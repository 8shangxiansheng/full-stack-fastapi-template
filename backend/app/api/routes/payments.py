import uuid
from datetime import datetime, timezone
from decimal import Decimal
import hmac
from hashlib import sha256
from json import JSONDecodeError, loads
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
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
    timestamp: int = Field(ge=0)
    payload: str
    signature: str = Field(max_length=255)


class PaymentCreatePublic(BaseModel):
    order_id: uuid.UUID
    provider: str
    out_trade_no: str
    amount: Decimal
    status: PaymentStatus


PAYMENT_STATUS_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCESS, PaymentStatus.FAILED},
    PaymentStatus.SUCCESS: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.REFUNDED: set(),
}


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


def _build_callback_signing_message(body: PaymentCallback) -> str:
    return f"{body.provider}:{body.transaction_id}:{body.timestamp}:{body.payload}"


def _verify_callback_timestamp(body: PaymentCallback) -> None:
    now = int(time.time())
    if abs(now - body.timestamp) > settings.PAYMENT_CALLBACK_TOLERANCE_SECONDS:
        raise HTTPException(status_code=400, detail="Callback timestamp expired")


def _verify_callback_signature(body: PaymentCallback) -> None:
    message = _build_callback_signing_message(body)
    expected_signature = hmac.new(
        settings.PAYMENT_CALLBACK_SIGNING_SECRET.encode(),
        message.encode(),
        sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, body.signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid callback signature",
        )


def _check_payment_transition(current: PaymentStatus, target: PaymentStatus) -> None:
    if current == target:
        return
    allowed = PAYMENT_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(status_code=400, detail="Invalid payment status transition")


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
    _verify_callback_timestamp(body)
    _verify_callback_signature(body)

    try:
        callback_data = loads(body.payload)
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid callback payload") from None

    out_trade_no = callback_data.get("out_trade_no")
    callback_status = callback_data.get("status")
    if not out_trade_no:
        raise HTTPException(status_code=400, detail="out_trade_no is required")

    replayed = session.exec(
        select(PaymentCallbackLog).where(
            PaymentCallbackLog.provider == body.provider,
            PaymentCallbackLog.transaction_id == body.transaction_id,
            PaymentCallbackLog.payload == body.payload,
            col(PaymentCallbackLog.processed).is_(True),
        )
    ).first()
    if replayed:
        raise HTTPException(status_code=409, detail="Callback replay detected")

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
    _check_payment_transition(payment.status, target_status)
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
