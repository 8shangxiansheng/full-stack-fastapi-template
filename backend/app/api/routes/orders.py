import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.models import Message

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    address_id: uuid.UUID


class OrderStatusChange(BaseModel):
    event: str = Field(max_length=64)
    reason: str | None = Field(default=None, max_length=255)


@router.get("/")
def read_orders(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve order list (skeleton)."""
    _ = (session, current_user)
    return []


@router.get("/{order_id}")
def read_order(
    order_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Retrieve order detail (skeleton)."""
    _ = (order_id, session, current_user)
    return {"id": str(order_id)}


@router.post("/", response_model=Message)
def create_order(
    body: OrderCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Create order from cart (skeleton)."""
    _ = (body, session, current_user)
    return Message(message="Order create skeleton endpoint")


@router.post("/{order_id}/status", response_model=Message)
def change_order_status(
    order_id: uuid.UUID,
    body: OrderStatusChange,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Change order status by event (skeleton)."""
    _ = (order_id, body, session, current_user)
    return Message(message="Order status change skeleton endpoint")
