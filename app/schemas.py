from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import BookingStatus, PaymentStatus

# ---------- Auth ----------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Diagnostic centres & tests ----------


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)


class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    centre_id: int
    name: str
    price: float


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    tests: List[TestOut] = []


# ---------- Bookings ----------


class BookingCreate(BaseModel):
    test_id: int
    appointment_time: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_time: datetime
    amount: float
    status: BookingStatus
    created_at: datetime


# ---------- Payments ----------


class PaymentCreate(BaseModel):
    booking_id: int
    # Testing/demo convenience only: lets a caller force the simulated
    # outcome instead of relying on the random default. Never present in a
    # real payment-gateway integration.
    simulate_result: Optional[Literal["SUCCESS", "FAILED"]] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    provider_reference: str
    status: PaymentStatus
    created_at: datetime


class WebhookPayload(BaseModel):
    """Shape of an inbound event from the simulated payment provider."""

    event_id: str = Field(min_length=1)
    payment_id: int
    status: Literal["SUCCESS", "FAILED"]
