import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.models import Message

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/categories")
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
    is_active: bool = Query(default=True),
) -> Any:
    """Retrieve menu categories (skeleton)."""
    _ = (session, current_user, is_active)
    return []


@router.get("/dishes")
def read_dishes(
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID | None = None,
    is_active: bool = Query(default=True),
) -> Any:
    """Retrieve dishes (skeleton)."""
    _ = (session, current_user, category_id, is_active)
    return []


@router.get("/dishes/{dish_id}/skus")
def read_dish_skus(
    dish_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Retrieve SKU list for a dish (skeleton)."""
    _ = (dish_id, session, current_user)
    return []


@router.post("/sync", response_model=Message)
def sync_menu(session: SessionDep, current_user: CurrentUser) -> Message:
    """Reserved endpoint for menu sync jobs (skeleton)."""
    _ = (session, current_user)
    return Message(message="Menu sync skeleton endpoint")
