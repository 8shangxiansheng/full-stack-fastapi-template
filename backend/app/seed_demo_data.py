import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine, init_db
from app.models import (
    Address,
    Cart,
    CartItem,
    Category,
    Dish,
    DishSku,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusLog,
    PaymentRecord,
    PaymentStatus,
    User,
    UserCreate,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_USER_EMAIL = "demo@example.com"
DEMO_USER_PASSWORD = "changethis"
DEMO_USER_NAME = "Demo User"
DEMO_CATEGORY_PREFIX = "[DEMO]"


def _order_no(prefix: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}{now}{uuid.uuid4().hex[:6].upper()}"


def _create_demo_user(session: Session) -> User:
    user = crud.get_user_by_email(session=session, email=DEMO_USER_EMAIL)
    if user:
        return user
    return crud.create_user(
        session=session,
        user_create=UserCreate(
            email=DEMO_USER_EMAIL,
            password=DEMO_USER_PASSWORD,
            full_name=DEMO_USER_NAME,
            is_superuser=False,
        ),
    )


def _reset_demo_data(session: Session) -> None:
    demo_user = crud.get_user_by_email(session=session, email=DEMO_USER_EMAIL)
    if demo_user:
        orders = session.exec(select(Order).where(Order.user_id == demo_user.id)).all()
        for order in orders:
            session.delete(order)

        addresses = session.exec(select(Address).where(Address.user_id == demo_user.id)).all()
        for address in addresses:
            session.delete(address)

        cart = session.exec(select(Cart).where(Cart.user_id == demo_user.id)).first()
        if cart:
            session.delete(cart)

        session.delete(demo_user)
        session.commit()

    demo_categories = session.exec(
        select(Category).where(Category.name.like(f"{DEMO_CATEGORY_PREFIX}%"))
    ).all()
    for category in demo_categories:
        session.delete(category)
    session.commit()


def _seed_menu(session: Session) -> list[DishSku]:
    category_specs = [
        {
            "name": f"{DEMO_CATEGORY_PREFIX} Meals",
            "sort_order": 1,
            "dishes": [
                {
                    "name": "Demo Chicken Rice",
                    "description": "Classic rice combo",
                    "skus": [
                        ("Regular", Decimal("24.90"), 80),
                        ("Large", Decimal("29.90"), 60),
                    ],
                },
                {
                    "name": "Demo Beef Noodles",
                    "description": "Braised beef soup noodles",
                    "skus": [("Standard", Decimal("26.90"), 70)],
                },
            ],
        },
        {
            "name": f"{DEMO_CATEGORY_PREFIX} Drinks",
            "sort_order": 2,
            "dishes": [
                {
                    "name": "Demo Lemon Tea",
                    "description": "Fresh brewed",
                    "skus": [
                        ("M", Decimal("8.90"), 120),
                        ("L", Decimal("10.90"), 120),
                    ],
                }
            ],
        },
    ]

    all_skus: list[DishSku] = []
    for category_spec in category_specs:
        category = Category(
            name=category_spec["name"],
            sort_order=category_spec["sort_order"],
            is_active=True,
        )
        session.add(category)
        session.commit()
        session.refresh(category)

        for dish_spec in category_spec["dishes"]:
            dish = Dish(
                category_id=category.id,
                name=dish_spec["name"],
                description=dish_spec["description"],
                is_active=True,
            )
            session.add(dish)
            session.commit()
            session.refresh(dish)

            for sku_name, sku_price, sku_stock in dish_spec["skus"]:
                sku = DishSku(
                    dish_id=dish.id,
                    name=sku_name,
                    price=sku_price,
                    stock=sku_stock,
                    is_active=True,
                )
                session.add(sku)
                session.commit()
                session.refresh(sku)
                all_skus.append(sku)

    return all_skus


def _seed_user_assets(session: Session, user: User, skus: list[DishSku]) -> None:
    address = Address(
        user_id=user.id,
        receiver_name="Demo Receiver",
        receiver_phone="13800000000",
        province="Shanghai",
        city="Shanghai",
        district="Pudong",
        detail="Demo Street 1",
        is_default=True,
    )
    session.add(address)
    session.commit()
    session.refresh(address)

    cart = Cart(user_id=user.id)
    session.add(cart)
    session.commit()
    session.refresh(cart)

    for sku, quantity in [(skus[0], 1), (skus[2], 2)]:
        session.add(
            CartItem(
                cart_id=cart.id,
                dish_sku_id=sku.id,
                quantity=quantity,
            )
        )
    session.commit()

    order_specs = [
        (OrderStatus.PENDING_PAYMENT, None, "seed_pending_payment", skus[0], 1),
        (OrderStatus.PAID, PaymentStatus.SUCCESS, "seed_paid", skus[1], 1),
        (OrderStatus.PREPARING, PaymentStatus.SUCCESS, "seed_preparing", skus[2], 2),
        (OrderStatus.DELIVERING, PaymentStatus.SUCCESS, "seed_delivering", skus[3], 1),
        (OrderStatus.COMPLETED, PaymentStatus.SUCCESS, "seed_completed", skus[4], 2),
        (
            OrderStatus.REFUND_PENDING,
            PaymentStatus.SUCCESS,
            "seed_refund_pending",
            skus[0],
            1,
        ),
        (OrderStatus.REFUNDED, PaymentStatus.REFUNDED, "seed_refunded", skus[1], 1),
    ]

    for order_status, payment_status, event, sku, quantity in order_specs:
        now = datetime.now(timezone.utc)
        line_amount = sku.price * quantity
        order = Order(
            user_id=user.id,
            address_id=address.id,
            order_no=_order_no("DM"),
            status=order_status,
            total_amount=line_amount,
            paid_at=now if payment_status else None,
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        dish = session.get(Dish, sku.dish_id)
        if not dish:
            raise RuntimeError("Demo dish not found")

        session.add(
            OrderItem(
                order_id=order.id,
                dish_sku_id=sku.id,
                dish_name_snapshot=dish.name,
                sku_name_snapshot=sku.name,
                unit_price=sku.price,
                quantity=quantity,
                line_amount=line_amount,
            )
        )
        session.add(
            OrderStatusLog(
                order_id=order.id,
                from_status=None,
                to_status=order_status,
                event=event,
                actor="seed_demo_data",
            )
        )

        if payment_status:
            session.add(
                PaymentRecord(
                    order_id=order.id,
                    provider="mockpay",
                    out_trade_no=_order_no("PT"),
                    amount=line_amount,
                    status=payment_status,
                    paid_at=now,
                )
            )

        session.commit()


def main() -> None:
    if settings.ENVIRONMENT != "local":
        raise RuntimeError("Demo seed can only run in local environment")

    with Session(engine) as session:
        init_db(session)
        _reset_demo_data(session)
        demo_user = _create_demo_user(session)
        demo_skus = _seed_menu(session)
        _seed_user_assets(session, demo_user, demo_skus)

    logger.info("Demo seed completed")
    logger.info("Demo user: %s / %s", DEMO_USER_EMAIL, DEMO_USER_PASSWORD)


if __name__ == "__main__":
    main()
