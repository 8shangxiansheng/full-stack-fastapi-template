from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.menu import create_random_dish_sku


def test_add_cart_item_and_read_cart(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)

    add_response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
        json={"dish_sku_id": str(sku.id), "quantity": 2},
    )
    assert add_response.status_code == 200

    read_response = client.get(
        f"{settings.API_V1_STR}/cart/",
        headers=normal_user_token_headers,
    )
    assert read_response.status_code == 200
    body = read_response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["dish_sku_id"] == str(sku.id)
    assert body["items"][0]["quantity"] == 2
    assert Decimal(body["total_amount"]) > Decimal("0")


def test_add_same_sku_merges_quantity(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)

    for quantity in [1, 3]:
        response = client.post(
            f"{settings.API_V1_STR}/cart/items",
            headers=normal_user_token_headers,
            json={"dish_sku_id": str(sku.id), "quantity": quantity},
        )
        assert response.status_code == 200

    read_response = client.get(
        f"{settings.API_V1_STR}/cart/",
        headers=normal_user_token_headers,
    )
    assert read_response.status_code == 200
    body = read_response.json()
    found = [item for item in body["items"] if item["dish_sku_id"] == str(sku.id)]
    assert len(found) == 1
    assert found[0]["quantity"] == 4


def test_update_and_delete_cart_item(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)

    add_response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
        json={"dish_sku_id": str(sku.id), "quantity": 1},
    )
    assert add_response.status_code == 200

    cart_response = client.get(
        f"{settings.API_V1_STR}/cart/",
        headers=normal_user_token_headers,
    )
    assert cart_response.status_code == 200
    items = cart_response.json()["items"]
    target_items = [item for item in items if item["dish_sku_id"] == str(sku.id)]
    assert len(target_items) == 1
    cart_item_id = target_items[0]["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/cart/items/{cart_item_id}",
        headers=normal_user_token_headers,
        json={"quantity": 5},
    )
    assert update_response.status_code == 200

    delete_response = client.delete(
        f"{settings.API_V1_STR}/cart/items/{cart_item_id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 200


def test_clear_cart(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)
    response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
        json={"dish_sku_id": str(sku.id), "quantity": 1},
    )
    assert response.status_code == 200

    clear_response = client.delete(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
    )
    assert clear_response.status_code == 200

    read_response = client.get(
        f"{settings.API_V1_STR}/cart/",
        headers=normal_user_token_headers,
    )
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["items"] == []
    assert Decimal(body["total_amount"]) == Decimal("0")


def test_add_cart_item_insufficient_stock(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)
    sku.stock = 1
    db.add(sku)
    db.commit()
    db.refresh(sku)

    response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
        json={"dish_sku_id": str(sku.id), "quantity": 2},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient stock"


def test_add_cart_item_inactive_sku(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    sku = create_random_dish_sku(db)
    sku.is_active = False
    db.add(sku)
    db.commit()
    db.refresh(sku)

    response = client.post(
        f"{settings.API_V1_STR}/cart/items",
        headers=normal_user_token_headers,
        json={"dish_sku_id": str(sku.id), "quantity": 1},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Dish SKU is not available"
