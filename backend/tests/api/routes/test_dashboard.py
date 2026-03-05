from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
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


def _seed_paid_order(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    email: str,
) -> None:
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

    create_order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json={"address_id": str(address.id)},
    )
    assert create_order_response.status_code == 200
    order_id = create_order_response.json()["id"]

    create_payment_response = client.post(
        f"{settings.API_V1_STR}/payments/create",
        headers=headers,
        json={"order_id": order_id, "provider": "mockpay"},
    )
    assert create_payment_response.status_code == 200
    out_trade_no = create_payment_response.json()["out_trade_no"]

    callback_response = client.post(
        f"{settings.API_V1_STR}/payments/callbacks",
        json=build_mockpay_callback_payload(out_trade_no=out_trade_no),
    )
    assert callback_response.status_code == 200


def test_dashboard_overview_normal_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_paid_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/overview",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["scope"] == "mine"
    assert body["menu"]["categories_total"] >= 1
    assert body["orders"]["total"] >= 1
    assert body["payments"]["total"] >= 1
    assert len(body["recent_orders"]) >= 1

    order_status_map = {
        item["status"]: item["count"] for item in body["orders"]["status_breakdown"]
    }
    assert order_status_map["paid"] >= 1

    payment_status_map = {
        item["status"]: item["count"] for item in body["payments"]["status_breakdown"]
    }
    assert payment_status_map["success"] >= 1


def test_dashboard_overview_superuser_scope(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_paid_order(client, db, normal_user_token_headers, settings.EMAIL_TEST_USER)

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/overview",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["scope"] == "all"
    assert body["orders"]["total"] >= 1
    assert body["payments"]["total"] >= 1
