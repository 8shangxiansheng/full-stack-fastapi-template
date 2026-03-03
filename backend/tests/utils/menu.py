import uuid
from decimal import Decimal

from sqlmodel import Session

from app.models import Category, Dish, DishSku
from tests.utils.utils import random_lower_string


def create_random_category(db: Session) -> Category:
    category = Category(name=f"cat-{random_lower_string()[:8]}", sort_order=0, is_active=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_random_dish(db: Session, category_id: uuid.UUID | None = None) -> Dish:
    category = create_random_category(db) if category_id is None else db.get(Category, category_id)
    if not category:
        raise Exception("Category not found")
    dish = Dish(
        category_id=category.id,
        name=f"dish-{random_lower_string()[:8]}",
        description="test dish",
        is_active=True,
    )
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def create_random_dish_sku(db: Session, dish_id: uuid.UUID | None = None) -> DishSku:
    dish = create_random_dish(db) if dish_id is None else db.get(Dish, dish_id)
    if not dish:
        raise Exception("Dish not found")
    sku = DishSku(
        dish_id=dish.id,
        name=f"sku-{random_lower_string()[:8]}",
        price=Decimal("19.90"),
        stock=100,
        is_active=True,
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku
