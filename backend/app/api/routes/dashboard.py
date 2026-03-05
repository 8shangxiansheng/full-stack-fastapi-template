from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Address,
    Cart,
    CartItem,
    Category,
    Dish,
    DishSku,
    Order,
    OrderStatus,
    PaymentRecord,
    PaymentStatus,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class StatusCount(BaseModel):
    status: str
    count: int


class MenuOverview(BaseModel):
    categories_total: int
    categories_active: int
    dishes_total: int
    dishes_active: int
    skus_total: int
    skus_active: int


class AddressOverview(BaseModel):
    total: int
    default_count: int


class CartOverview(BaseModel):
    items_count: int
    total_amount: Decimal


class OrdersOverview(BaseModel):
    total: int
    today: int
    realized_gmv: Decimal
    status_breakdown: list[StatusCount]


class PaymentsOverview(BaseModel):
    total: int
    success_amount: Decimal
    status_breakdown: list[StatusCount]


class RecentOrder(BaseModel):
    id: str
    order_no: str
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime | None = None


class DashboardOverview(BaseModel):
    scope: str
    menu: MenuOverview
    addresses: AddressOverview
    cart: CartOverview
    orders: OrdersOverview
    payments: PaymentsOverview
    recent_orders: list[RecentOrder]


def _enum_to_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _to_int(value: Any) -> int:
    return int(value or 0)


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _apply_order_scope(statement: Any, current_user: CurrentUser) -> Any:
    if not current_user.is_superuser:
        return statement.where(Order.user_id == current_user.id)
    return statement


def _apply_payment_scope(statement: Any, current_user: CurrentUser) -> Any:
    if not current_user.is_superuser:
        return statement.join(Order, PaymentRecord.order_id == Order.id).where(
            Order.user_id == current_user.id
        )
    return statement


def _menu_overview(session: SessionDep) -> MenuOverview:
    categories_total = session.exec(select(func.count(Category.id))).one()
    categories_active = session.exec(
        select(func.count(Category.id)).where(Category.is_active.is_(True))
    ).one()
    dishes_total = session.exec(select(func.count(Dish.id))).one()
    dishes_active = session.exec(
        select(func.count(Dish.id)).where(Dish.is_active.is_(True))
    ).one()
    skus_total = session.exec(select(func.count(DishSku.id))).one()
    skus_active = session.exec(
        select(func.count(DishSku.id)).where(DishSku.is_active.is_(True))
    ).one()
    return MenuOverview(
        categories_total=_to_int(categories_total),
        categories_active=_to_int(categories_active),
        dishes_total=_to_int(dishes_total),
        dishes_active=_to_int(dishes_active),
        skus_total=_to_int(skus_total),
        skus_active=_to_int(skus_active),
    )


def _address_overview(session: SessionDep, current_user: CurrentUser) -> AddressOverview:
    total = session.exec(
        select(func.count(Address.id)).where(Address.user_id == current_user.id)
    ).one()
    default_count = session.exec(
        select(func.count(Address.id)).where(
            Address.user_id == current_user.id,
            Address.is_default.is_(True),
        )
    ).one()
    return AddressOverview(total=_to_int(total), default_count=_to_int(default_count))


def _cart_overview(session: SessionDep, current_user: CurrentUser) -> CartOverview:
    cart_id = session.exec(select(Cart.id).where(Cart.user_id == current_user.id)).first()
    if not cart_id:
        return CartOverview(items_count=0, total_amount=Decimal("0"))

    items_count = session.exec(
        select(func.count(CartItem.id)).where(CartItem.cart_id == cart_id)
    ).one()
    total_amount = session.exec(
        select(func.coalesce(func.sum(DishSku.price * CartItem.quantity), 0))
        .select_from(CartItem)
        .join(DishSku, CartItem.dish_sku_id == DishSku.id)
        .where(CartItem.cart_id == cart_id)
    ).one()
    return CartOverview(
        items_count=_to_int(items_count),
        total_amount=_to_decimal(total_amount),
    )


def _orders_overview(session: SessionDep, current_user: CurrentUser) -> OrdersOverview:
    start_of_today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    total = session.exec(
        _apply_order_scope(select(func.count(Order.id)), current_user)
    ).one()
    today = session.exec(
        _apply_order_scope(
            select(func.count(Order.id)).where(Order.created_at >= start_of_today),
            current_user,
        )
    ).one()
    order_status_rows = session.exec(
        _apply_order_scope(
            select(Order.status, func.count(Order.id)).group_by(Order.status),
            current_user,
        )
    ).all()
    order_counts = {_enum_to_value(status): _to_int(count) for status, count in order_status_rows}

    realized_statuses = (
        OrderStatus.PAID,
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARING,
        OrderStatus.READY_FOR_DELIVERY,
        OrderStatus.DELIVERING,
        OrderStatus.COMPLETED,
        OrderStatus.REFUND_PENDING,
        OrderStatus.REFUND_REJECTED,
    )
    realized_gmv = session.exec(
        _apply_order_scope(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.status.in_(realized_statuses)
            ),
            current_user,
        )
    ).one()

    return OrdersOverview(
        total=_to_int(total),
        today=_to_int(today),
        realized_gmv=_to_decimal(realized_gmv),
        status_breakdown=[
            StatusCount(status=status.value, count=order_counts.get(status.value, 0))
            for status in OrderStatus
        ],
    )


def _payments_overview(session: SessionDep, current_user: CurrentUser) -> PaymentsOverview:
    total = session.exec(
        _apply_payment_scope(select(func.count(PaymentRecord.id)), current_user)
    ).one()
    success_amount = session.exec(
        _apply_payment_scope(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.status == PaymentStatus.SUCCESS
            ),
            current_user,
        )
    ).one()
    payment_status_rows = session.exec(
        _apply_payment_scope(
            select(PaymentRecord.status, func.count(PaymentRecord.id)).group_by(
                PaymentRecord.status
            ),
            current_user,
        )
    ).all()
    payment_counts = {
        _enum_to_value(status): _to_int(count) for status, count in payment_status_rows
    }
    return PaymentsOverview(
        total=_to_int(total),
        success_amount=_to_decimal(success_amount),
        status_breakdown=[
            StatusCount(status=status.value, count=payment_counts.get(status.value, 0))
            for status in PaymentStatus
        ],
    )


@router.get("/overview", response_model=DashboardOverview)
def read_dashboard_overview(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve dashboard aggregate overview for current scope."""
    menu = _menu_overview(session)
    addresses = _address_overview(session, current_user)
    cart = _cart_overview(session, current_user)
    orders = _orders_overview(session, current_user)
    payments = _payments_overview(session, current_user)
    recent_orders = session.exec(
        _apply_order_scope(
            select(Order).order_by(col(Order.created_at).desc()).limit(5),
            current_user,
        )
    ).all()

    return DashboardOverview(
        scope="all" if current_user.is_superuser else "mine",
        menu=menu,
        addresses=addresses,
        cart=cart,
        orders=orders,
        payments=payments,
        recent_orders=[
            RecentOrder(
                id=str(order.id),
                order_no=order.order_no,
                status=order.status,
                total_amount=order.total_amount,
                created_at=order.created_at,
            )
            for order in recent_orders
        ],
    )
