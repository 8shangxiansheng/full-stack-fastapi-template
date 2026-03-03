import uuid
from datetime import datetime, timezone
from decimal import Decimal
from json import JSONDecodeError, loads
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Order,
    OrderStatus,
    OrderStatusLog,
    PaymentCallbackLog,
    PaymentRecord,
    PaymentStatus,
)

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCreate(BaseModel):
    order_id: uuid.UUID
    provider: str = Field(max_length=32)


class PaymentCallback(BaseModel):
    provider: str = Field(max_length=32)
    transaction_id: str = Field(max_length=128)
    payload: str
    signature: str | None = Field(default=None, max_length=255)


class PaymentCreatePublic(BaseModel):
    order_id: uuid.UUID
    provider: str
    out_trade_no: str
    amount: Decimal
    status: PaymentStatus


def _load_order_or_404(session: SessionDep, order_id: uuid.UUID) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _check_order_owner(order: Order, current_user: CurrentUser) -> None:
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _build_out_trade_no() -> str:
    return f"PT{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


@router.post("/create", response_model=PaymentCreatePublic)
def create_payment(
    body: PaymentCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> PaymentCreatePublic:
    """Create payment request for an order."""
    order = _load_order_or_404(session, body.order_id)
    _check_order_owner(order, current_user)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=400, detail="Order is not pending payment")

    existing = session.exec(
        select(PaymentRecord)
        .where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.provider == body.provider,
            PaymentRecord.status == PaymentStatus.PENDING,
        )
        .order_by(col(PaymentRecord.created_at).desc())
    ).first()
    if existing:
        return PaymentCreatePublic(
            order_id=existing.order_id,
            provider=existing.provider,
            out_trade_no=existing.out_trade_no,
            amount=existing.amount,
            status=existing.status,
        )

    payment = PaymentRecord(
        order_id=order.id,
        provider=body.provider,
        out_trade_no=_build_out_trade_no(),
        amount=order.total_amount,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return PaymentCreatePublic(
        order_id=payment.order_id,
        provider=payment.provider,
        out_trade_no=payment.out_trade_no,
        amount=payment.amount,
        status=payment.status,
    )


@router.post("/callbacks", response_model=PaymentCreatePublic)
def payment_callback(body: PaymentCallback, session: SessionDep) -> Any:
    """
    Handle payment callback.

    Payload format:
    {"out_trade_no":"...", "status":"success|failed|refunded"}
    """
    callback_log = PaymentCallbackLog(
        provider=body.provider,
        transaction_id=body.transaction_id,
        payload=body.payload,
        signature=body.signature,
        processed=False,
    )
    session.add(callback_log)
    session.commit()
    session.refresh(callback_log)

    try:
        callback_data = loads(body.payload)
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid callback payload") from None

    out_trade_no = callback_data.get("out_trade_no")
    callback_status = callback_data.get("status")
    if not out_trade_no:
        raise HTTPException(status_code=400, detail="out_trade_no is required")

    payment = session.exec(
        select(PaymentRecord).where(
            PaymentRecord.provider == body.provider,
            PaymentRecord.out_trade_no == out_trade_no,
        )
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    status_map = {
        "success": PaymentStatus.SUCCESS,
        "failed": PaymentStatus.FAILED,
        "refunded": PaymentStatus.REFUNDED,
    }
    if callback_status not in status_map:
        raise HTTPException(status_code=400, detail="Invalid callback status")

    target_status = status_map[callback_status]
    if payment.status == target_status:
        callback_log.processed = True
        session.add(callback_log)
        session.commit()
        return PaymentCreatePublic(
            order_id=payment.order_id,
            provider=payment.provider,
            out_trade_no=payment.out_trade_no,
            amount=payment.amount,
            status=payment.status,
        )

    payment.status = target_status
    if target_status == PaymentStatus.SUCCESS:
        payment.paid_at = datetime.now(timezone.utc)
        order = _load_order_or_404(session, payment.order_id)
        if order.status == OrderStatus.PENDING_PAYMENT:
            previous_status = order.status
            order.status = OrderStatus.PAID
            order.paid_at = payment.paid_at
            session.add(order)
            session.add(
                OrderStatusLog(
                    order_id=order.id,
                    from_status=previous_status,
                    to_status=OrderStatus.PAID,
                    event="pay",
                    actor="payment_callback",
                )
            )

    callback_log.processed = True
    session.add(payment)
    session.add(callback_log)
    session.commit()
    session.refresh(payment)
    return PaymentCreatePublic(
        order_id=payment.order_id,
        provider=payment.provider,
        out_trade_no=payment.out_trade_no,
        amount=payment.amount,
        status=payment.status,
    )
