from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import PaymentCallbackLog, PaymentRecord, PaymentStatus, User
from tests.utils.address import create_random_address
from tests.utils.menu import create_random_dish_sku
from tests.utils.payment import build_mockpay_callback_payload


def _current_user(db: Session, email: str) -> User:
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if not user:
        raise Exception("User not found")
    return user


def _clear_cart(client: TestClient, headers: dict[str, str]) -> None:
    response = client.delete(f"{settings.API_V1_STR}/cart/items", headers=headers)
    assert response.status_code == 200


def _create_pending_order(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    email: str,
) -> dict:
    _clear_cart(client, headers)
    user = _current_user(db, email)
    sku = create_random_dish_sku(db)
    address = create_random_address(db, user=user, is_default=True)

    add_response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=headers,
        json={"dish_sku_id": str(sku.id), "quantity": 1},
    )
    assert add_response.status_code == 200

    create_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json={"address_id": str(address.id)},
    )
    assert create_response.status_code == 200
    return create_response.json()


def test_create_payment_success(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)

    response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == order["id"]
    assert body["provider"] == "mockpay"
    assert body["status"] == "pending"
    assert body["out_trade_no"].startswith("PT")


def test_payment_callback_updates_order_paid(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]

    callback_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=build_mockpay_callback_payload(out_trade_no=out_trade_no),
    )
    assert callback_response.status_code == 200
    assert callback_response.json()["status"] == "success"

    order_response = client.get(
        f"{settings.API_V1_STR}/orders/{order['id']}",
        headers=normal_user_token_headers,
    )
    assert order_response.status_code == 200
    assert order_response.json()["status"] == "paid"


def test_payment_callback_replay_rejected(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]
    callback_payload = build_mockpay_callback_payload(out_trade_no=out_trade_no)

    first_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=callback_payload,
    )
    assert first_response.status_code == 200

    replay_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=callback_payload,
    )
    assert replay_response.status_code == 409
    assert replay_response.json()["detail"] == "Callback replay detected"

    payment = db.exec(select(PaymentRecord).where(PaymentRecord.out_trade_no == out_trade_no)).first()
    if not payment:
        raise Exception("Payment record not found")
    assert payment.status == PaymentStatus.SUCCESS

    callbacks = db.exec(
        select(PaymentCallbackLog).where(PaymentCallbackLog.transaction_id == out_trade_no)
    ).all()
    assert len(callbacks) == 1
    assert all(item.processed is True for item in callbacks)


def test_payment_callback_invalid_signature(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]
    callback_payload = build_mockpay_callback_payload(out_trade_no=out_trade_no)
    callback_payload["signature"] = "invalid-signature"

    callback_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=callback_payload,
    )
    assert callback_response.status_code == 401
    assert callback_response.json()["detail"] == "Invalid callback signature"


def test_payment_callback_expired_timestamp(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]
    expired_timestamp = 1
    callback_payload = build_mockpay_callback_payload(
        out_trade_no=out_trade_no,
        timestamp=expired_timestamp,
    )

    callback_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=callback_payload,
    )
    assert callback_response.status_code == 400
    assert callback_response.json()["detail"] == "Callback timestamp expired"


def test_payment_callback_rejects_invalid_transition(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order = _create_pending_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=normal_user_token_headers,
        json={"order_id": order["id"], "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]

    success_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=build_mockpay_callback_payload(out_trade_no=out_trade_no),
    )
    assert success_response.status_code == 200

    failed_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=build_mockpay_callback_payload(
            out_trade_no=out_trade_no,
            callback_status="failed",
            transaction_id=f"{out_trade_no}-failed",
        ),
    )
    assert failed_response.status_code == 400
    assert failed_response.json()["detail"] == "Invalid payment status transition"

    payment = db.exec(select(PaymentRecord).where(PaymentRecord.out_trade_no == out_trade_no)).first()
    if not payment:
        raise Exception("Payment record not found")
    assert payment.status == PaymentStatus.SUCCESS
