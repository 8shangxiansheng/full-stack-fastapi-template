import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.models import Message

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCreate(BaseModel):
    order_id: uuid.UUID
    provider: str = Field(max_length=32)


class PaymentCallback(BaseModel):
    provider: str = Field(max_length=32)
    transaction_id: str = Field(max_length=128)
    payload: str
    signature: str | None = Field(default=None, max_length=255)


@router.post("/create", response_model=Message)
def create_payment(
    body: PaymentCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Create payment request (skeleton)."""
    _ = (body, session, current_user)
    return Message(message="Payment create skeleton endpoint")


@router.post("/callbacks", response_model=Message)
def payment_callback(body: PaymentCallback, session: SessionDep) -> Message:
    """Handle payment callback (skeleton)."""
    _ = (body, session)
    return Message(message="Payment callback skeleton endpoint")
