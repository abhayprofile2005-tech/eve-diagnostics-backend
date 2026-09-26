# EVE Healthcare — Diagnostics Booking API

Backend service for diagnostic test bookings and simulated payments, built for the
EVE Healthcare SDE Intern assignment.

**Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, JWT auth (python-jose), PostgreSQL
(SQLite for local/dev/tests). Interactive API docs (Swagger UI) are generated
automatically by FastAPI — no extra work required to get them.

---

## 1. Running it locally

### Option A — quickest (SQLite, no Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# optional: seed a couple of diagnostic centres/tests so Swagger UI isn't empty
python -m scripts.seed_data

uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI. Tables are created
automatically on startup — no migration step needed.

### Option B — Docker Compose (API + PostgreSQL)

```bash
docker compose up --build
```

This starts a PostgreSQL container and the API together, with the API pointed at
Postgres via `DATABASE_URL` (see `docker-compose.yml`). API is at
**http://127.0.0.1:8000/docs**.

### Configuration

Copy `.env.example` to `.env` to override any setting locally. Everything has a
sane default so the app runs with zero configuration out of the box.

### Running tests

```bash
pip install -r requirements.txt   # if not already installed
pytest -v
```

Tests run against an isolated SQLite file (`test_eve_diagnostics.db`, auto-created
and reset before every test) — no PostgreSQL or Docker required to run them.

---

## 2. API endpoints

All request/response bodies are JSON except login, which is an OAuth2 form
(`application/x-www-form-urlencoded`) so Swagger UI's built-in "Authorize" button
works out of the box.

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create a user |
| POST | `/auth/login` | — | Get a JWT (`username`=email, `password`) |

```bash
curl -X POST localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"supersecret1","full_name":"Demo User"}'

curl -X POST localhost:8000/auth/login \
  -d "username=demo@example.com&password=supersecret1"
# -> {"access_token": "...", "token_type": "bearer"}
```

Use the token as `Authorization: Bearer <token>` on every endpoint below marked
"auth".

### Diagnostic centres & tests

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/centres/` | ✓ | Create a diagnostic centre |
| GET | `/centres/` | — | List centres (with their tests) |
| GET | `/centres/{id}` | — | Get one centre |
| POST | `/centres/{id}/tests/` | ✓ | Add a test to a centre |
| GET | `/tests/?centre_id=` | — | List tests, optionally filtered by centre |

```bash
curl -X POST localhost:8000/centres/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"City Diagnostics","location":"Prayagraj"}'

curl -X POST localhost:8000/centres/1/tests/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Complete Blood Count","price":650}'
```

### Bookings

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings/` | ✓ | Book a test (status starts `PENDING`) |
| GET | `/bookings/` | ✓ | List your own bookings |
| GET | `/bookings/{id}` | ✓ | Get one booking (must be yours — `403` otherwise) |
| POST | `/bookings/{id}/cancel` | ✓ | Cancel a `PENDING`/`FAILED` booking |

```bash
curl -X POST localhost:8000/bookings/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test_id":1,"appointment_time":"2026-10-05T10:00:00"}'
```

`amount` is always taken from the test's current price server-side — never
trust a client-supplied amount.

### Payments & webhook

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | ✓ | Simulate a payment attempt for a booking |
| POST | `/payments/webhook/` | shared secret | Simulated provider callback (**idempotent**) |

```bash
# Force an outcome for demoing (optional — random SUCCESS/FAILED if omitted)
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"booking_id":1,"simulate_result":"SUCCESS"}'

# Provider webhook (note: NOT user-JWT-protected — it's authenticated by a
# shared secret instead, since the caller is the payment provider, not a user)
curl -X POST localhost:8000/payments/webhook/ \
  -H "X-Webhook-Secret: dev-webhook-secret" -H "Content-Type: application/json" \
  -d '{"event_id":"evt_123","payment_id":1,"status":"SUCCESS"}'
```

Redelivering the exact same `event_id` any number of times is safe — see
"Idempotency design" below.

---

## 3. Database / schema design

```
User 1───* Booking *───1 DiagnosticTest *───1 DiagnosticCentre
              │
              1
              │
              *
           Payment
              │
              *
              │
        WebhookEvent (event_id UNIQUE)
```

- **User** — email/password (bcrypt-hashed).
- **DiagnosticCentre → DiagnosticTest** — one-to-many; a test always belongs to
  exactly one centre and carries its own price.
- **Booking** — references `user`, `test`, and (denormalized) `centre_id`
  copied from the test at creation time, so listing a user's bookings never
  needs a join through `test → centre` just to show which centre it's at.
  `amount` is copied from the test's price at booking time too, so a later
  price change never silently alters an existing booking's amount.
- **Payment** — one-to-many from `Booking`, *not* one-to-one: a failed payment
  can be retried, producing a second `Payment` row against the same booking.
  Only one `PENDING` payment is allowed per booking at a time (checked in
  `POST /payments/`).
- **WebhookEvent** — the idempotency ledger; see below.

Booking states: `PENDING → CONFIRMED` (payment succeeded) or `PENDING → FAILED`
(payment failed, retryable) or `→ CANCELLED` (user-cancelled, only from
`PENDING`/`FAILED`). Payment states: `PENDING → SUCCESS` / `PENDING → FAILED`.

## 4. Idempotency design (webhook)

This was the part of the spec called out as most important, so it got the most
deliberate design:

1. **Event ledger.** Every webhook call's `event_id` is inserted into
   `webhook_events` under a **unique constraint**. A redelivery of the same
   `event_id` hits that constraint, is caught, and short-circuits to an
   `"already_processed"` response *before* touching any payment/booking state.
2. **Idempotent state transition, independent of #1.** The actual
   payment→booking state change lives in one function
   (`_apply_payment_result`) that is a no-op unless the payment is still
   `PENDING`. Both `POST /payments/` (synchronous simulation) and
   `POST /payments/webhook/` (async callback) call this same function, so
   there is exactly one code path to reason about, and a webhook that arrives
   late for an *already-resolved* payment can't flip its state.

These two layers are deliberately redundant (defense in depth): #1 stops
duplicate *deliveries*; #2 stops any accidental double-application even if two
different event_ids somehow raced for the same payment.

---

## 5. Assumptions

- No separate admin/staff role — any authenticated user can create diagnostic
  centres and tests. A real deployment would restrict this to a staff role.
- Payments are purely simulated in-process (random or caller-forced outcome);
  there's no actual async gateway, so `POST /payments/` resolves synchronously.
  The webhook endpoint models the *shape* of an async provider callback and is
  independently idempotent, as if it were arriving on its own schedule.
- The webhook is authenticated by a shared secret header rather than a real
  provider's HMAC signature scheme, to keep the simulation self-contained.
- Booking `GET`/cancel return `403` (not `404`) when a booking exists but
  belongs to someone else, to make the authorization check explicit for this
  assignment's edge-case criterion — a public-facing API might prefer `404`
  to avoid confirming a booking ID exists at all.
- Tables are created via `Base.metadata.create_all()` at startup rather than
  Alembic migrations, to keep the assignment's scope focused (see below).

## 6. What I'd improve with more time

- Alembic migrations instead of `create_all()`, for real schema evolution.
- Role-based access control (staff/admin role for managing centres/tests).
- Rate limiting on `/auth/login` and the webhook endpoint.
- Structured JSON logging + request-id middleware for traceability.
- Pagination on `GET /bookings/` and `GET /centres/`.
- Retry-with-backoff + dead-letter handling for webhook processing failures.
- Redis-backed caching for the centre/test catalog (read-heavy, rarely changes).
