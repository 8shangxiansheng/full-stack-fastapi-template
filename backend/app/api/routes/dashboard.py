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


def _order_scope_statement(current_user: CurrentUser) -> Any:
    statement = select(Order)
    if not current_user.is_superuser:
        statement = statement.where(Order.user_id == current_user.id)
    return statement


def _order_status_count_statement(current_user: CurrentUser) -> Any:
    statement = select(Order.status, func.count(Order.id)).group_by(Order.status)
    if not current_user.is_superuser:
        statement = statement.where(Order.user_id == current_user.id)
    return statement


def _payment_scope_statement(current_user: CurrentUser) -> Any:
    statement = select(PaymentRecord)
    if not current_user.is_superuser:
        statement = statement.join(Order, PaymentRecord.order_id == Order.id).where(
            Order.user_id == current_user.id
        )
    return statement


def _payment_status_count_statement(current_user: CurrentUser) -> Any:
    statement = (
        select(PaymentRecord.status, func.count(PaymentRecord.id))
        .select_from(PaymentRecord)
        .group_by(PaymentRecord.status)
    )
    if not current_user.is_superuser:
        statement = statement.join(Order, PaymentRecord.order_id == Order.id).where(
            Order.user_id == current_user.id
        )
    return statement


@router.get("/overview", response_model=DashboardOverview)
def read_dashboard_overview(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve dashboard aggregate overview for current scope."""
    order_statement = _order_scope_statement(current_user)
    payment_statement = _payment_scope_statement(current_user)

    categories = session.exec(select(Category)).all()
    dishes = session.exec(select(Dish)).all()
    skus = session.exec(select(DishSku)).all()

    address_list = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    cart_items = (
        session.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all() if cart else []
    )

    cart_total = Decimal("0")
    for item in cart_items:
        sku = session.get(DishSku, item.dish_sku_id)
        if not sku:
            continue
        cart_total += sku.price * item.quantity

    orders = session.exec(order_statement).all()
    order_status_rows = session.exec(_order_status_count_statement(current_user)).all()
    order_counts = {_enum_to_value(status): int(count) for status, count in order_status_rows}

    start_of_today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_count = len(
        [order for order in orders if order.created_at and order.created_at >= start_of_today]
    )

    realized_statuses = {
        OrderStatus.PAID,
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARING,
        OrderStatus.READY_FOR_DELIVERY,
        OrderStatus.DELIVERING,
        OrderStatus.COMPLETED,
        OrderStatus.REFUND_PENDING,
        OrderStatus.REFUND_REJECTED,
    }
    realized_gmv = sum(
        (
            order.total_amount
            for order in orders
            if order.status in realized_statuses and order.total_amount is not None
        ),
        Decimal("0"),
    )

    payments = session.exec(payment_statement).all()
    payment_status_rows = session.exec(_payment_status_count_statement(current_user)).all()
    payment_counts = {
        _enum_to_value(status): int(count) for status, count in payment_status_rows
    }
    success_amount = sum(
        (
            payment.amount
            for payment in payments
            if payment.status == PaymentStatus.SUCCESS and payment.amount is not None
        ),
        Decimal("0"),
    )

    recent_orders = session.exec(
        order_statement.order_by(col(Order.created_at).desc()).limit(5)
    ).all()

    return DashboardOverview(
        scope="all" if current_user.is_superuser else "mine",
        menu=MenuOverview(
            categories_total=len(categories),
            categories_active=len([category for category in categories if category.is_active]),
            dishes_total=len(dishes),
            dishes_active=len([dish for dish in dishes if dish.is_active]),
            skus_total=len(skus),
            skus_active=len([sku for sku in skus if sku.is_active]),
        ),
        addresses=AddressOverview(
            total=len(address_list),
            default_count=len([address for address in address_list if address.is_default]),
        ),
        cart=CartOverview(items_count=len(cart_items), total_amount=cart_total),
        orders=OrdersOverview(
            total=len(orders),
            today=today_count,
            realized_gmv=realized_gmv,
            status_breakdown=[
                StatusCount(status=status.value, count=order_counts.get(status.value, 0))
                for status in OrderStatus
            ],
        ),
        payments=PaymentsOverview(
            total=len(payments),
            success_amount=success_amount,
            status_breakdown=[
                StatusCount(status=status.value, count=payment_counts.get(status.value, 0))
                for status in PaymentStatus
            ],
        ),
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
