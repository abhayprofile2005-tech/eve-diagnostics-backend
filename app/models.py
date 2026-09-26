import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    # Stored naive-UTC: every datetime in this schema is UTC by convention,
    # so we drop tzinfo rather than mixing naive/aware values across a
    # SQLite (naive-only) vs. PostgreSQL (aware-capable) deployment.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    bookings = relationship("Booking", back_populates="user")


class DiagnosticCentre(Base):
    __tablename__ = "diagnostic_centres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    tests = relationship(
        "DiagnosticTest", back_populates="centre", cascade="all, delete-orphan"
    )


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("diagnostic_centres.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)

    centre = relationship("DiagnosticCentre", back_populates="tests")
    bookings = relationship("Booking", back_populates="test")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("diagnostic_tests.id"), nullable=False)
    # Denormalized for cheap reads (avoids a join through test -> centre on
    # every booking list/detail call). Always set from test.centre_id at
    # creation time, so it can never disagree with the source of truth.
    centre_id = Column(Integer, ForeignKey("diagnostic_centres.id"), nullable=False)

    appointment_time = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(
        Enum(BookingStatus), nullable=False, default=BookingStatus.PENDING
    )

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="bookings")
    test = relationship("DiagnosticTest", back_populates="bookings")
    centre = relationship("DiagnosticCentre")
    payments = relationship(
        "Payment", back_populates="booking", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)

    # Stands in for the payment gateway's own reference / transaction id.
    provider_reference = Column(String, unique=True, default=_uuid)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    booking = relationship("Booking", back_populates="payments")


class WebhookEvent(Base):
    """
    Records every payment-provider event we've successfully processed, keyed
    by the provider's event_id. This is the idempotency ledger: a webhook
    delivery whose event_id is already here is acknowledged but not
    reprocessed, regardless of how many times the provider retries it.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_webhook_event_id"),)

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    status = Column(String, nullable=False)
    received_at = Column(DateTime, default=_utcnow)
