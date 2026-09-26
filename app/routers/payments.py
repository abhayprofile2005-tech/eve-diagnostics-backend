import random
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, Payment, PaymentStatus, User, WebhookEvent

router = APIRouter(prefix="/payments", tags=["payments"])


def _apply_payment_result(db: Session, payment: Payment, result_status: str) -> Payment:
    """
    The single place that transitions a Payment + its Booking based on a
    provider result. Both POST /payments/ (the synchronous simulation) and
    POST /payments/webhook/ (the async provider callback) funnel through
    here, so there is exactly one state-transition code path to reason
    about and test.

    Idempotent by construction: if the payment has already left PENDING,
    the result is not reapplied — we just return the existing state. This
    is a second line of defence behind the WebhookEvent ledger in the
    webhook endpoint below (belt-and-suspenders against races/retries).
    """
    if payment.status != PaymentStatus.PENDING:
        return payment

    payment.status = PaymentStatus.SUCCESS if result_status == "SUCCESS" else PaymentStatus.FAILED

    booking = payment.booking
    booking.status = (
        BookingStatus.CONFIRMED if result_status == "SUCCESS" else BookingStatus.FAILED
    )

    db.commit()
    db.refresh(payment)
    return payment


@router.post("/", response_model=schemas.PaymentOut, status_code=status.HTTP_201_CREATED)
def initiate_payment(
    payload: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulates calling out to a payment gateway for a booking. No real
    gateway is involved: the outcome is either the caller-supplied
    `simulate_result` (handy for demos/tests) or a random SUCCESS/FAILED
    otherwise, exactly like the assignment asks for.
    """
    booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this booking",
        )
    if booking.status not in (BookingStatus.PENDING, BookingStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking is {booking.status.value} and cannot accept a new payment",
        )
    # Guard against a second payment attempt racing/duplicating an
    # already-in-flight one for the same booking.
    in_flight = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id, Payment.status == PaymentStatus.PENDING)
        .first()
    )
    if in_flight:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A payment is already in progress for this booking",
        )

    booking.status = BookingStatus.PENDING  # reactivate a previously-FAILED booking
    payment = Payment(
        booking_id=booking.id,
        provider_reference=uuid.uuid4().hex,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    result = payload.simulate_result or random.choice(["SUCCESS", "FAILED"])
    payment = _apply_payment_result(db, payment, result)
    return payment


@router.post("/webhook/", status_code=status.HTTP_200_OK)
def payment_webhook(
    payload: schemas.WebhookPayload,
    db: Session = Depends(get_db),
    x_webhook_secret: str = Header(default=""),
):
    """
    Receives asynchronous status updates from the (simulated) payment
    provider. Must be safe to call more than once with the same event_id --
    providers commonly retry webhook deliveries on timeout, and this must
    never create duplicate payments/bookings or double-apply a transition.

    Idempotency strategy (defence in depth):
      1. `event_id` is recorded in webhook_events under a unique constraint.
         A duplicate delivery hits that constraint and is acknowledged
         without reprocessing.
      2. Even if two requests for a *new* event_id somehow race each other,
         `_apply_payment_result` only ever acts once because it no-ops once
         the payment has left PENDING.
    """
    if x_webhook_secret != settings.webhook_shared_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    payment = db.query(Payment).filter(Payment.id == payload.payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    event = WebhookEvent(
        event_id=payload.event_id,
        payment_id=payment.id,
        status=payload.status,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # event_id already recorded -> this exact event was already
        # processed. Acknowledge without touching payment/booking state.
        db.rollback()
        return {"status": "already_processed", "payment_id": payment.id}

    payment = _apply_payment_result(db, payment, payload.status)
    return {"status": "processed", "payment_id": payment.id, "payment_status": payment.status.value}
