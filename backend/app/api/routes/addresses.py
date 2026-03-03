import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.models import Message

router = APIRouter(prefix="/addresses", tags=["addresses"])


class AddressCreate(BaseModel):
    receiver_name: str = Field(max_length=255)
    receiver_phone: str = Field(max_length=32)
    province: str = Field(max_length=100)
    city: str = Field(max_length=100)
    district: str = Field(max_length=100)
    detail: str = Field(max_length=255)
    is_default: bool = False


class AddressUpdate(BaseModel):
    receiver_name: str | None = Field(default=None, max_length=255)
    receiver_phone: str | None = Field(default=None, max_length=32)
    province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    detail: str | None = Field(default=None, max_length=255)
    is_default: bool | None = None


@router.get("/")
def read_addresses(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve address list (skeleton)."""
    _ = (session, current_user)
    return []


@router.post("/", response_model=Message)
def create_address(
    body: AddressCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Create a new address (skeleton)."""
    _ = (body, session, current_user)
    return Message(message="Address create skeleton endpoint")


@router.patch("/{address_id}", response_model=Message)
def update_address(
    address_id: uuid.UUID,
    body: AddressUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Update address (skeleton)."""
    _ = (address_id, body, session, current_user)
    return Message(message="Address update skeleton endpoint")


@router.delete("/{address_id}", response_model=Message)
def delete_address(
    address_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete address (skeleton)."""
    _ = (address_id, session, current_user)
    return Message(message="Address delete skeleton endpoint")
