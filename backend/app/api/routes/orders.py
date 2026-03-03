import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, delete, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Address,
    Cart,
    CartItem,
    Dish,
    DishSku,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusLog,
)

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    address_id: uuid.UUID


class OrderStatusChange(BaseModel):
    event: str = Field(max_length=64)
    reason: str | None = Field(default=None, max_length=255)


class OrderItemPublic(BaseModel):
    id: uuid.UUID
    dish_sku_id: uuid.UUID | None
    dish_name_snapshot: str
    sku_name_snapshot: str
    unit_price: Decimal
    quantity: int
    line_amount: Decimal


class OrderStatusLogPublic(BaseModel):
    id: uuid.UUID
    from_status: OrderStatus | None
    to_status: OrderStatus
    event: str
    actor: str
    reason: str | None
    created_at: datetime | None = None


class OrderPublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    address_id: uuid.UUID | None
    order_no: str
    status: OrderStatus
    total_amount: Decimal
    paid_at: datetime | None = None
    created_at: datetime | None = None


class OrderDetailPublic(OrderPublic):
    items: list[OrderItemPublic]
    status_logs: list[OrderStatusLogPublic]


ORDER_STATUS_TRANSITIONS: dict[str, dict[OrderStatus, OrderStatus]] = {
    "pay": {OrderStatus.PENDING_PAYMENT: OrderStatus.PAID},
    "merchant_accept": {OrderStatus.PAID: OrderStatus.ACCEPTED},
    "start_preparing": {OrderStatus.ACCEPTED: OrderStatus.PREPARING},
    "ready_for_delivery": {OrderStatus.PREPARING: OrderStatus.READY_FOR_DELIVERY},
    "dispatch": {OrderStatus.READY_FOR_DELIVERY: OrderStatus.DELIVERING},
    "complete": {OrderStatus.DELIVERING: OrderStatus.COMPLETED},
    "cancel": {
        OrderStatus.PENDING_PAYMENT: OrderStatus.CANCELLED,
        OrderStatus.PAID: OrderStatus.CANCELLED,
        OrderStatus.ACCEPTED: OrderStatus.CANCELLED,
        OrderStatus.PREPARING: OrderStatus.CANCELLED,
        OrderStatus.READY_FOR_DELIVERY: OrderStatus.CANCELLED,
    },
    "request_refund": {
        OrderStatus.PAID: OrderStatus.REFUND_PENDING,
        OrderStatus.ACCEPTED: OrderStatus.REFUND_PENDING,
        OrderStatus.PREPARING: OrderStatus.REFUND_PENDING,
        OrderStatus.READY_FOR_DELIVERY: OrderStatus.REFUND_PENDING,
        OrderStatus.DELIVERING: OrderStatus.REFUND_PENDING,
        OrderStatus.COMPLETED: OrderStatus.REFUND_PENDING,
    },
    "approve_refund": {OrderStatus.REFUND_PENDING: OrderStatus.REFUNDED},
    "reject_refund": {OrderStatus.REFUND_PENDING: OrderStatus.REFUND_REJECTED},
}


def _check_order_owner(order: Order, current_user: CurrentUser) -> None:
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _load_order_or_404(session: SessionDep, order_id: uuid.UUID) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _build_order_detail(session: SessionDep, order: Order) -> OrderDetailPublic:
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(col(OrderItem.created_at))
    ).all()
    status_logs = session.exec(
        select(OrderStatusLog)
        .where(OrderStatusLog.order_id == order.id)
        .order_by(col(OrderStatusLog.created_at))
    ).all()
    return OrderDetailPublic(
        **order.model_dump(),
        items=[OrderItemPublic(**item.model_dump()) for item in order_items],
        status_logs=[OrderStatusLogPublic(**log.model_dump()) for log in status_logs],
    )


def _generate_order_no() -> str:
    return f"OD{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


@router.get("/", response_model=list[OrderPublic])
def read_orders(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve order list."""
    statement = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(col(Order.created_at).desc())
    )
    return session.exec(statement).all()


@router.get("/{order_id}", response_model=OrderDetailPublic)
def read_order(
    order_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Retrieve order detail."""
    order = _load_order_or_404(session, order_id)
    _check_order_owner(order, current_user)
    return _build_order_detail(session, order)


@router.post("/", response_model=OrderDetailPublic)
def create_order(
    body: OrderCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderDetailPublic:
    """Create order from current cart."""
    address = session.get(Address, body.address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    if address.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")
    cart_items = session.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    if len(cart_items) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    prepared_items: list[tuple[CartItem, DishSku, Dish, Decimal]] = []
    total_amount = Decimal("0")
    for cart_item in cart_items:
        sku = session.get(DishSku, cart_item.dish_sku_id)
        if not sku:
            raise HTTPException(status_code=404, detail="Dish SKU not found")
        dish = session.get(Dish, sku.dish_id)
        if not dish:
            raise HTTPException(status_code=404, detail="Dish not found")
        if not sku.is_active or not dish.is_active:
            raise HTTPException(status_code=400, detail="Dish SKU is not available")
        if cart_item.quantity > sku.stock:
            raise HTTPException(status_code=400, detail="Insufficient stock")

        line_amount = sku.price * cart_item.quantity
        total_amount += line_amount
        prepared_items.append((cart_item, sku, dish, line_amount))

    order = Order(
        user_id=current_user.id,
        address_id=address.id,
        order_no=_generate_order_no(),
        status=OrderStatus.PENDING_PAYMENT,
        total_amount=total_amount,
    )
    session.add(order)
    session.flush()

    for cart_item, sku, dish, line_amount in prepared_items:
        order_item = OrderItem(
            order_id=order.id,
            dish_sku_id=sku.id,
            dish_name_snapshot=dish.name,
            sku_name_snapshot=sku.name,
            unit_price=sku.price,
            quantity=cart_item.quantity,
            line_amount=line_amount,
        )
        sku.stock -= cart_item.quantity
        session.add(order_item)
        session.add(sku)

    session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.PENDING_PAYMENT,
            event="create_order",
            actor="user",
        )
    )
    session.exec(delete(CartItem).where(CartItem.cart_id == cart.id))
    session.commit()
    session.refresh(order)
    return _build_order_detail(session, order)


@router.post("/{order_id}/status", response_model=OrderDetailPublic)
def change_order_status(
    order_id: uuid.UUID,
    body: OrderStatusChange,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderDetailPublic:
    """Change order status by event."""
    order = _load_order_or_404(session, order_id)
    _check_order_owner(order, current_user)

    transitions = ORDER_STATUS_TRANSITIONS.get(body.event)
    if not transitions:
        raise HTTPException(status_code=400, detail="Invalid order event")
    next_status = transitions.get(order.status)
    if not next_status:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    previous = order.status
    order.status = next_status
    if next_status == OrderStatus.PAID:
        order.paid_at = datetime.now(timezone.utc)
    session.add(order)
    session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=previous,
            to_status=next_status,
            event=body.event,
            actor="superuser" if current_user.is_superuser else "user",
            reason=body.reason,
        )
    )
    session.commit()
    session.refresh(order)
    return _build_order_detail(session, order)
