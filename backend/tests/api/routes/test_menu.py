from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.menu import create_random_category, create_random_dish


def test_create_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    payload = {"name": "主食", "sort_order": 1, "is_active": True}
    response = client.post(
        f"{settings.API_V1_STR}/menu/categories",
        headers=superuser_token_headers,
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["sort_order"] == payload["sort_order"]
    assert body["is_active"] is payload["is_active"]


def test_create_category_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    payload = {"name": "饮品", "sort_order": 2, "is_active": True}
    response = client.post(
        f"{settings.API_V1_STR}/menu/categories",
        headers=normal_user_token_headers,
        json=payload,
    )
    assert response.status_code == 403


def test_read_dishes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    dish = create_random_dish(db)
    response = client.get(
        f"{settings.API_V1_STR}/menu/dishes",
        headers=superuser_token_headers,
        params={"category_id": str(dish.category_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert any(item["id"] == str(dish.id) for item in body)


def test_create_sku_and_read_skus(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    dish = create_random_dish(db)
    payload = {
        "name": "大份",
        "price": str(Decimal("22.50")),
        "stock": 20,
        "is_active": True,
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/menu/dishes/{dish.id}/skus",
        headers=superuser_token_headers,
        json=payload,
    )
    assert create_response.status_code == 200

    list_response = client.get(
        f"{settings.API_V1_STR}/menu/dishes/{dish.id}/skus",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) >= 1
    assert any(item["name"] == payload["name"] for item in body)


def test_update_dish_category_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    category = create_random_category(db)
    dish = create_random_dish(db, category.id)
    payload = {"category_id": "203c1a91-f65f-4018-b1f5-5fd94f36ef58"}
    response = client.patch(
        f"{settings.API_V1_STR}/menu/dishes/{dish.id}",
        headers=superuser_token_headers,
        json=payload,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"
