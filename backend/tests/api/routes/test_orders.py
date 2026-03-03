import uuid
from json import dumps

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import DishSku, PaymentRecord, PaymentStatus, User
from tests.utils.address import create_random_address
from tests.utils.menu import create_random_dish_sku
from tests.utils.user import authentication_token_from_email, create_random_user


def _current_user(db: Session, email: str) -> User:
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if not user:
        raise Exception("User not found")
    return user


def _clear_cart(client: TestClient, headers: dict[str, str]) -> None:
    response = client.delete(f"{settings.API_V1_STR}/cart/items", headers=headers)
    assert response.status_code == 200


def _create_order(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    email: str,
) -> tuple[dict, DishSku]:
    _clear_cart(client, headers)
    user = _current_user(db, email)
    sku = create_random_dish_sku(db)
    address = create_random_address(db, user=user, is_default=True)

    add_response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=headers,
        json={"dish_sku_id": str(sku.id), "quantity": 2},
    )
    assert add_response.status_code == 200

    create_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json={"address_id": str(address.id)},
    )
    assert create_response.status_code == 200
    return create_response.json(), sku


def _pay_order(
    client: TestClient,
    headers: dict[str, str],
    order_id: str,
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=headers,
        json={"order_id": order_id, "provider": "mockpay"},
    )
    assert create_response.status_code == 200
    out_trade_no = create_response.json()["out_trade_no"]

    callback_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json={
            "provider": "mockpay",
            "transaction_id": out_trade_no,
            "payload": dumps({"out_trade_no": out_trade_no, "status": "success"}),
            "signature": "test-signature",
        },
    )
    assert callback_response.status_code == 200


def test_create_order_success(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    body, sku = _create_order(
        client,
        db,
        normal_user_token_headers,
        settings.EMAIL_TEST_USER,
    )
    assert body["status"] == "pending_payment"
    assert len(body["items"]) == 1
    assert body["total_amount"] == body["items"][0]["line_amount"]
    assert body["status_logs"][0]["event"] == "create_order"

    cart_response = client.get(
        f"{settings.API_V1_STR}/cart/",
        headers=normal_user_token_headers,
    )
    assert cart_response.status_code == 200
    assert cart_response.json()["items"] == []

    db.refresh(sku)
    assert sku.stock == 98


def test_create_order_empty_cart(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    _clear_cart(client, normal_user_token_headers)
    user = _current_user(db, settings.EMAIL_TEST_USER)
    address = create_random_address(db, user=user, is_default=True)

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=normal_user_token_headers,
        json={"address_id": str(address.id)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cart is empty"


def test_read_orders_only_current_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    _create_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    current_user = _current_user(db, settings.EMAIL_TEST_USER)
    other_user = create_random_user(db)
    other_headers = authentication_token_from_email(
        client=client,
        email=other_user.email,
        db=db,
    )
    _create_order(client, db, other_headers, other_user.email)

    response = client.get(f"{settings.API_V1_STR}/orders/", headers=normal_user_token_headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 1
    assert all(order["user_id"] == str(current_user.id) for order in orders)


def test_read_order_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    other_user = create_random_user(db)
    other_headers = authentication_token_from_email(
        client=client,
        email=other_user.email,
        db=db,
    )
    order_body, _ = _create_order(client, db, other_headers, other_user.email)

    response = client.get(
        f"{settings.API_V1_STR}/orders/{order_body['id']}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_change_order_status(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    order_body, _ = _create_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)

    pay_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=normal_user_token_headers,
        json={"event": "pay"},
    )
    assert pay_response.status_code == 403
    assert pay_response.json()["detail"] == "Not enough permissions"

    invalid_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=normal_user_token_headers,
        json={"event": "pay"},
    )
    assert invalid_response.status_code == 403
    assert invalid_response.json()["detail"] == "Not enough permissions"


def test_superuser_read_orders_all_users(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _create_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    other_user = create_random_user(db)
    other_headers = authentication_token_from_email(
        client=client,
        email=other_user.email,
        db=db,
    )
    _create_order(client, db, other_headers, other_user.email)

    response = client.get(
        f"{settings.API_V1_STR}/orders/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    orders = response.json()
    user_ids = {order["user_id"] for order in orders}
    assert len(user_ids) >= 2


def test_superuser_can_run_merchant_event(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    order_body, _ = _create_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)

    pay_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=superuser_token_headers,
        json={"event": "pay"},
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "paid"

    accept_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=superuser_token_headers,
        json={"event": "merchant_accept"},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"


def test_refund_approval_updates_payment_status(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    order_body, _ = _create_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)
    _pay_order(client, normal_user_token_headers, order_body["id"])

    request_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=normal_user_token_headers,
        json={"event": "request_refund"},
    )
    assert request_response.status_code == 200
    assert request_response.json()["status"] == "refund_pending"

    approve_response = client.post(
        f"{settings.API_V1_STR}/orders/{order_body['id']}/status",
        headers=superuser_token_headers,
        json={"event": "approve_refund"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "refunded"

    payment = db.exec(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == uuid.UUID(order_body["id"]))
        .order_by(PaymentRecord.created_at.desc())
    ).first()
    if not payment:
        raise Exception("Payment record not found")
    assert payment.status == PaymentStatus.REFUNDED
