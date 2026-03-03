from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Address, User
from tests.utils.address import create_random_address
from tests.utils.user import create_random_user


def _current_user(db: Session, email: str) -> User:
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if not user:
        raise Exception("User not found")
    return user


def test_create_address_default_rule(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    payload = {
        "receiver_name": "李四",
        "receiver_phone": "13900000000",
        "province": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "detail": "灵隐路 8 号",
    }

    response = client.post(
        f"{settings.API_V1_STR}/addresses/",
        headers=normal_user_token_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is True


def test_create_address_set_new_default(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    user = _current_user(db, settings.EMAIL_TEST_USER)
    create_random_address(db, user=user, is_default=True)

    payload = {
        "receiver_name": "王五",
        "receiver_phone": "13700000000",
        "province": "江苏省",
        "city": "南京市",
        "district": "玄武区",
        "detail": "中山路 3 号",
        "is_default": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/addresses/",
        headers=normal_user_token_headers,
        json=payload,
    )
    assert response.status_code == 200

    addresses = db.exec(select(Address).where(Address.user_id == user.id)).all()
    default_addresses = [item for item in addresses if item.is_default]
    assert len(default_addresses) == 1


def test_update_address_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    another_user = create_random_user(db)
    address = create_random_address(db, user=another_user)

    response = client.patch(
        f"{settings.API_V1_STR}/addresses/{address.id}",
        headers=normal_user_token_headers,
        json={"detail": "更新后的地址"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_address_promote_latest_default(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    user = _current_user(db, settings.EMAIL_TEST_USER)
    first = create_random_address(db, user=user, is_default=True)
    second = create_random_address(db, user=user, is_default=False)

    response = client.delete(
        f"{settings.API_V1_STR}/addresses/{first.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200

    db.expire_all()
    promoted = db.get(Address, second.id)
    if not promoted:
        raise Exception("Promoted address not found")
    assert promoted.is_default is True


def test_read_addresses(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    user = _current_user(db, settings.EMAIL_TEST_USER)
    create_random_address(db, user=user, is_default=True)

    response = client.get(
        f"{settings.API_V1_STR}/addresses/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert "receiver_name" in body[0]
