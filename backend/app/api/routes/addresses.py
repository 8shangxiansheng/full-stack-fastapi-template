import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Address, Message

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


class AddressPublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    receiver_name: str
    receiver_phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool
    created_at: datetime | None = None


def _unset_other_default_addresses(session: SessionDep, user_id: uuid.UUID, keep_id: uuid.UUID | None = None) -> None:
    statement = select(Address).where(Address.user_id == user_id, Address.is_default)
    addresses = session.exec(statement).all()
    for address in addresses:
        if keep_id and address.id == keep_id:
            continue
        address.is_default = False
        session.add(address)


def _get_address_or_404(session: SessionDep, address_id: uuid.UUID) -> Address:
    address = session.get(Address, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address


@router.get("/", response_model=list[AddressPublic])
def read_addresses(session: SessionDep, current_user: CurrentUser) -> Any:
    """Retrieve current user's addresses."""
    statement = (
        select(Address)
        .where(Address.user_id == current_user.id)
        .order_by(col(Address.is_default).desc(), col(Address.created_at).desc())
    )
    return session.exec(statement).all()


@router.post("/", response_model=AddressPublic)
def create_address(
    body: AddressCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Address:
    """Create a new address."""
    existing = session.exec(select(Address).where(Address.user_id == current_user.id)).all()
    is_default = body.is_default or len(existing) == 0

    address = Address.model_validate(body, update={"user_id": current_user.id, "is_default": is_default})
    if is_default:
        _unset_other_default_addresses(session, current_user.id)

    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.patch("/{address_id}", response_model=AddressPublic)
def update_address(
    address_id: uuid.UUID,
    body: AddressUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Address:
    """Update address."""
    address = _get_address_or_404(session, address_id)
    if address.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = body.model_dump(exclude_unset=True)
    if update_dict.get("is_default") is True:
        _unset_other_default_addresses(session, current_user.id, keep_id=address.id)

    address.sqlmodel_update(update_dict)
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.delete("/{address_id}", response_model=Message)
def delete_address(
    address_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete address."""
    address = _get_address_or_404(session, address_id)
    if address.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    was_default = address.is_default
    session.delete(address)
    session.commit()

    if was_default:
        next_address = session.exec(
            select(Address)
            .where(Address.user_id == current_user.id)
            .order_by(col(Address.created_at).desc())
        ).first()
        if next_address:
            next_address.is_default = True
            session.add(next_address)
            session.commit()

    return Message(message="Address deleted successfully")
