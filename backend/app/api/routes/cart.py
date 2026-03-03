import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.models import Message

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemAdd(BaseModel):
    dish_sku_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


@router.get("/")
def read_cart(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve current user's cart (skeleton)."""
    _ = (session, current_user)
    return {"items": [], "total_amount": 0}


@router.post("/items", response_model=Message)
def add_cart_item(
    body: CartItemAdd,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Add an item to cart (skeleton)."""
    _ = (body, session, current_user)
    return Message(message="Cart add item skeleton endpoint")


@router.patch("/items/{cart_item_id}", response_model=Message)
def update_cart_item(
    cart_item_id: uuid.UUID,
    body: CartItemUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Update cart item quantity (skeleton)."""
    _ = (cart_item_id, body, session, current_user)
    return Message(message="Cart update item skeleton endpoint")


@router.delete("/items/{cart_item_id}", response_model=Message)
def delete_cart_item(
    cart_item_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete a cart item (skeleton)."""
    _ = (cart_item_id, session, current_user)
    return Message(message="Cart delete item skeleton endpoint")


@router.delete("/items", response_model=Message)
def clear_cart(session: SessionDep, current_user: CurrentUser) -> Message:
    """Clear all cart items (skeleton)."""
    _ = (session, current_user)
    return Message(message="Cart clear skeleton endpoint")
