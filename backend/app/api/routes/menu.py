from collections import defaultdict
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import Category, Dish, DishSku, Message

router = APIRouter(prefix="/menu", tags=["menu"])


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryPublic(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime | None = None


class DishCreate(BaseModel):
    category_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class DishUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class DishPublic(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None


class DishSkuCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0)
    stock: int = Field(default=0, ge=0)
    is_active: bool = True


class DishSkuUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class DishSkuPublic(BaseModel):
    id: uuid.UUID
    dish_id: uuid.UUID
    name: str
    price: Decimal
    stock: int
    is_active: bool
    created_at: datetime | None = None


class DishWithSkusPublic(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    skus: list[DishSkuPublic] = Field(default_factory=list)


@router.get("/categories", response_model=list[CategoryPublic])
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
    is_active: bool | None = None,
) -> Any:
    """Retrieve menu categories."""
    _ = current_user
    statement = select(Category).order_by(col(Category.sort_order), col(Category.created_at))
    if is_active is not None:
        statement = statement.where(Category.is_active == is_active)
    return session.exec(statement).all()


@router.post(
    "/categories",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CategoryPublic,
)
def create_category(*, session: SessionDep, body: CategoryCreate) -> Any:
    """Create a category."""
    category = Category.model_validate(body)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch(
    "/categories/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CategoryPublic,
)
def update_category(*, session: SessionDep, category_id: uuid.UUID, body: CategoryUpdate) -> Any:
    """Update a category."""
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    update_dict = body.model_dump(exclude_unset=True)
    category.sqlmodel_update(update_dict)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete(
    "/categories/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_category(*, session: SessionDep, category_id: uuid.UUID) -> Message:
    """Delete a category."""
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    session.delete(category)
    session.commit()
    return Message(message="Category deleted successfully")


@router.get("/dishes", response_model=list[DishPublic])
def read_dishes(
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve dishes."""
    _ = current_user
    statement = select(Dish).order_by(col(Dish.created_at).desc()).offset(skip).limit(limit)
    if category_id:
        statement = statement.where(Dish.category_id == category_id)
    if is_active is not None:
        statement = statement.where(Dish.is_active == is_active)
    return session.exec(statement).all()


@router.get("/dishes-with-skus", response_model=list[DishWithSkusPublic])
def read_dishes_with_skus(
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve dishes with sku list in one aggregated payload."""
    _ = current_user
    dish_statement = (
        select(Dish).order_by(col(Dish.created_at).desc()).offset(skip).limit(limit)
    )
    if category_id:
        dish_statement = dish_statement.where(Dish.category_id == category_id)
    if is_active is not None:
        dish_statement = dish_statement.where(Dish.is_active == is_active)

    dishes = session.exec(dish_statement).all()
    if not dishes:
        return []

    dish_ids = [dish.id for dish in dishes]
    sku_statement = (
        select(DishSku)
        .where(col(DishSku.dish_id).in_(dish_ids))
        .order_by(col(DishSku.created_at))
    )
    if is_active is not None:
        sku_statement = sku_statement.where(DishSku.is_active == is_active)

    skus_by_dish: dict[uuid.UUID, list[DishSku]] = defaultdict(list)
    for sku in session.exec(sku_statement).all():
        skus_by_dish[sku.dish_id].append(sku)

    return [
        DishWithSkusPublic(
            id=dish.id,
            category_id=dish.category_id,
            name=dish.name,
            description=dish.description,
            is_active=dish.is_active,
            created_at=dish.created_at,
            skus=[
                DishSkuPublic.model_validate(sku, from_attributes=True)
                for sku in skus_by_dish[dish.id]
            ],
        )
        for dish in dishes
    ]


@router.post(
    "/dishes",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DishPublic,
)
def create_dish(*, session: SessionDep, body: DishCreate) -> Any:
    """Create a dish."""
    category = session.get(Category, body.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    dish = Dish.model_validate(body)
    session.add(dish)
    session.commit()
    session.refresh(dish)
    return dish


@router.patch(
    "/dishes/{dish_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DishPublic,
)
def update_dish(*, session: SessionDep, dish_id: uuid.UUID, body: DishUpdate) -> Any:
    """Update a dish."""
    dish = session.get(Dish, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    update_dict = body.model_dump(exclude_unset=True)
    category_id = update_dict.get("category_id")
    if category_id:
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    dish.sqlmodel_update(update_dict)
    session.add(dish)
    session.commit()
    session.refresh(dish)
    return dish


@router.delete(
    "/dishes/{dish_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_dish(*, session: SessionDep, dish_id: uuid.UUID) -> Message:
    """Delete a dish."""
    dish = session.get(Dish, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    session.delete(dish)
    session.commit()
    return Message(message="Dish deleted successfully")


@router.get("/dishes/{dish_id}/skus", response_model=list[DishSkuPublic])
def read_dish_skus(
    dish_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    is_active: bool | None = None,
) -> Any:
    """Retrieve SKU list for a dish."""
    _ = current_user
    dish = session.get(Dish, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    statement = select(DishSku).where(DishSku.dish_id == dish_id).order_by(col(DishSku.created_at))
    if is_active is not None:
        statement = statement.where(DishSku.is_active == is_active)
    return session.exec(statement).all()


@router.post(
    "/dishes/{dish_id}/skus",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DishSkuPublic,
)
def create_dish_sku(*, dish_id: uuid.UUID, session: SessionDep, body: DishSkuCreate) -> Any:
    """Create a dish SKU."""
    dish = session.get(Dish, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    sku = DishSku.model_validate(body, update={"dish_id": dish_id})
    session.add(sku)
    session.commit()
    session.refresh(sku)
    return sku


@router.patch(
    "/skus/{sku_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DishSkuPublic,
)
def update_dish_sku(*, sku_id: uuid.UUID, session: SessionDep, body: DishSkuUpdate) -> Any:
    """Update a dish SKU."""
    sku = session.get(DishSku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="Dish SKU not found")
    update_dict = body.model_dump(exclude_unset=True)
    sku.sqlmodel_update(update_dict)
    session.add(sku)
    session.commit()
    session.refresh(sku)
    return sku


@router.delete(
    "/skus/{sku_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_dish_sku(*, sku_id: uuid.UUID, session: SessionDep) -> Message:
    """Delete a dish SKU."""
    sku = session.get(DishSku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="Dish SKU not found")
    session.delete(sku)
    session.commit()
    return Message(message="Dish SKU deleted successfully")
