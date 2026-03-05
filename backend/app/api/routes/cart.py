import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import delete, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Cart, CartItem, Dish, DishSku, Message

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemAdd(BaseModel):
    dish_sku_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemPublic(BaseModel):
    id: uuid.UUID
    dish_sku_id: uuid.UUID
    dish_name: str
    sku_name: str
    unit_price: Decimal
    quantity: int
    line_amount: Decimal
    stock: int
    is_active: bool


class CartPublic(BaseModel):
    items: list[CartItemPublic]
    total_amount: Decimal


def _get_or_create_cart(session: SessionDep, user_id: uuid.UUID) -> Cart:
    statement = select(Cart).where(Cart.user_id == user_id)
    cart = session.exec(statement).first()
    if cart:
        return cart

    cart = Cart(user_id=user_id)
    session.add(cart)
    session.commit()
    session.refresh(cart)
    return cart


def _check_cart_owner(cart: Cart, current_user: CurrentUser) -> None:
    if cart.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _load_available_sku(session: SessionDep, dish_sku_id: uuid.UUID) -> DishSku:
    sku = session.get(DishSku, dish_sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="Dish SKU not found")

    dish = session.get(Dish, sku.dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    if not sku.is_active or not dish.is_active:
        raise HTTPException(status_code=400, detail="Dish SKU is not available")

    return sku


@router.get("/", response_model=CartPublic)
def read_cart(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve current user's cart."""
    cart = _get_or_create_cart(session, current_user.id)
    statement = (
        select(CartItem, DishSku, Dish)
        .join(DishSku, DishSku.id == CartItem.dish_sku_id, isouter=True)
        .join(Dish, Dish.id == DishSku.dish_id, isouter=True)
        .where(CartItem.cart_id == cart.id)
    )
    cart_rows = session.exec(statement).all()

    result_items: list[CartItemPublic] = []
    total_amount = Decimal("0")

    for item, sku, dish in cart_rows:
        if sku is None or dish is None:
            continue

        line_amount = sku.price * item.quantity
        total_amount += line_amount
        result_items.append(
            CartItemPublic(
                id=item.id,
                dish_sku_id=sku.id,
                dish_name=dish.name,
                sku_name=sku.name,
                unit_price=sku.price,
                quantity=item.quantity,
                line_amount=line_amount,
                stock=sku.stock,
                is_active=(sku.is_active and dish.is_active),
            )
        )

    return CartPublic(items=result_items, total_amount=total_amount)


@router.post("/items", response_model=Message)
def add_cart_item(
    body: CartItemAdd,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Add an item to cart, merge quantity when same SKU exists."""
    sku = _load_available_sku(session, body.dish_sku_id)
    cart = _get_or_create_cart(session, current_user.id)

    statement = select(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.dish_sku_id == body.dish_sku_id,
    )
    existing = session.exec(statement).first()

    if existing:
        new_quantity = existing.quantity + body.quantity
        if new_quantity > sku.stock:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        existing.quantity = new_quantity
        session.add(existing)
        session.commit()
        return Message(message="Cart item quantity updated")

    if body.quantity > sku.stock:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    new_item = CartItem(
        cart_id=cart.id,
        dish_sku_id=body.dish_sku_id,
        quantity=body.quantity,
    )
    session.add(new_item)
    session.commit()
    return Message(message="Cart item added successfully")


@router.patch("/items/{cart_item_id}", response_model=Message)
def update_cart_item(
    cart_item_id: uuid.UUID,
    body: CartItemUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Update cart item quantity."""
    cart_item = session.get(CartItem, cart_item_id)
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    cart = session.get(Cart, cart_item.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    _check_cart_owner(cart, current_user)

    sku = _load_available_sku(session, cart_item.dish_sku_id)
    if body.quantity > sku.stock:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    cart_item.quantity = body.quantity
    session.add(cart_item)
    session.commit()
    return Message(message="Cart item updated successfully")


@router.delete("/items/{cart_item_id}", response_model=Message)
def delete_cart_item(
    cart_item_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete a cart item."""
    cart_item = session.get(CartItem, cart_item_id)
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    cart = session.get(Cart, cart_item.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    _check_cart_owner(cart, current_user)

    session.delete(cart_item)
    session.commit()
    return Message(message="Cart item deleted successfully")


@router.delete("/items", response_model=Message)
def clear_cart(session: SessionDep, current_user: CurrentUser) -> Message:
    """Clear all cart items for current user."""
    cart = _get_or_create_cart(session, current_user.id)
    statement = delete(CartItem).where(CartItem.cart_id == cart.id)
    session.exec(statement)
    session.commit()
    return Message(message="Cart cleared successfully")
