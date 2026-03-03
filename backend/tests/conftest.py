from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    Address,
    Cart,
    CartItem,
    Category,
    Dish,
    DishSku,
    Item,
    Order,
    OrderItem,
    OrderStatusLog,
    PaymentCallbackLog,
    PaymentRecord,
    User,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(PaymentCallbackLog)
        session.execute(statement)
        statement = delete(PaymentRecord)
        session.execute(statement)
        statement = delete(OrderStatusLog)
        session.execute(statement)
        statement = delete(OrderItem)
        session.execute(statement)
        statement = delete(Order)
        session.execute(statement)
        statement = delete(Address)
        session.execute(statement)
        statement = delete(CartItem)
        session.execute(statement)
        statement = delete(Cart)
        session.execute(statement)
        statement = delete(DishSku)
        session.execute(statement)
        statement = delete(Dish)
        session.execute(statement)
        statement = delete(Category)
        session.execute(statement)
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
