def test_signup_creates_user(api):
    resp = api.post(
        "/auth/signup",
        json={"email": "bob@example.com", "password": "supersecret1", "full_name": "Bob"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "bob@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_signup_duplicate_email_rejected(api):
    payload = {"email": "bob@example.com", "password": "supersecret1"}
    api.post("/auth/signup", json=payload)
    resp = api.post("/auth/signup", json=payload)
    assert resp.status_code == 409


def test_login_success_returns_token(api):
    api.post("/auth/signup", json={"email": "carol@example.com", "password": "supersecret1"})
    resp = api.post("/auth/login", data={"username": "carol@example.com", "password": "supersecret1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_rejected(api):
    api.post("/auth/signup", json={"email": "dave@example.com", "password": "supersecret1"})
    resp = api.post("/auth/login", data={"username": "dave@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_protected_route_requires_token(api):
    resp = api.get("/bookings/")
    assert resp.status_code == 401
