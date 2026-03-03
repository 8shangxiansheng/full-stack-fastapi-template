import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import DateTime, Numeric, String
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    carts: list["Cart"] = Relationship(back_populates="user", cascade_delete=True)
    addresses: list["Address"] = Relationship(back_populates="user", cascade_delete=True)
    orders: list["Order"] = Relationship(back_populates="user", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY_FOR_DELIVERY = "ready_for_delivery"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    REFUND_REJECTED = "refund_rejected"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, index=True)
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    dishes: list["Dish"] = Relationship(back_populates="category", cascade_delete=True)


class Dish(SQLModel, table=True):
    __tablename__ = "dish"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_id: uuid.UUID = Field(
        foreign_key="category.id", nullable=False, ondelete="CASCADE"
    )
    name: str = Field(max_length=255, index=True)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    category: Category | None = Relationship(back_populates="dishes")
    skus: list["DishSku"] = Relationship(back_populates="dish", cascade_delete=True)


class DishSku(SQLModel, table=True):
    __tablename__ = "dish_sku"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dish_id: uuid.UUID = Field(foreign_key="dish.id", nullable=False, ondelete="CASCADE")
    name: str = Field(max_length=255)
    price: Decimal = Field(sa_type=Numeric(10, 2))
    stock: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    dish: Dish | None = Relationship(back_populates="skus")
    cart_items: list["CartItem"] = Relationship(back_populates="dish_sku")
    order_items: list["OrderItem"] = Relationship(back_populates="dish_sku")


class Cart(SQLModel, table=True):
    __tablename__ = "cart"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", unique=True, index=True
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    user: User | None = Relationship(back_populates="carts")
    items: list["CartItem"] = Relationship(back_populates="cart", cascade_delete=True)


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cart_id: uuid.UUID = Field(
        foreign_key="cart.id", nullable=False, ondelete="CASCADE", index=True
    )
    dish_sku_id: uuid.UUID = Field(foreign_key="dish_sku.id", nullable=False, index=True)
    quantity: int = Field(default=1, ge=1)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    cart: Cart | None = Relationship(back_populates="items")
    dish_sku: DishSku | None = Relationship(back_populates="cart_items")


class Address(SQLModel, table=True):
    __tablename__ = "address"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    receiver_name: str = Field(max_length=255)
    receiver_phone: str = Field(max_length=32)
    province: str = Field(max_length=100)
    city: str = Field(max_length=100)
    district: str = Field(max_length=100)
    detail: str = Field(max_length=255)
    is_default: bool = Field(default=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    user: User | None = Relationship(back_populates="addresses")
    orders: list["Order"] = Relationship(back_populates="address")


class Order(SQLModel, table=True):
    __tablename__ = "customer_order"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    address_id: uuid.UUID | None = Field(default=None, foreign_key="address.id")
    order_no: str = Field(sa_type=String(32), unique=True, index=True)
    status: OrderStatus = Field(
        default=OrderStatus.PENDING_PAYMENT, sa_type=String(32), index=True
    )
    total_amount: Decimal = Field(sa_type=Numeric(10, 2))
    paid_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    user: User | None = Relationship(back_populates="orders")
    address: Address | None = Relationship(back_populates="orders")
    items: list["OrderItem"] = Relationship(back_populates="order", cascade_delete=True)
    status_logs: list["OrderStatusLog"] = Relationship(
        back_populates="order", cascade_delete=True
    )
    payments: list["PaymentRecord"] = Relationship(
        back_populates="order", cascade_delete=True
    )


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="customer_order.id", nullable=False, ondelete="CASCADE", index=True
    )
    dish_sku_id: uuid.UUID | None = Field(default=None, foreign_key="dish_sku.id")
    dish_name_snapshot: str = Field(max_length=255)
    sku_name_snapshot: str = Field(max_length=255)
    unit_price: Decimal = Field(sa_type=Numeric(10, 2))
    quantity: int = Field(ge=1)
    line_amount: Decimal = Field(sa_type=Numeric(10, 2))
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    order: Order | None = Relationship(back_populates="items")
    dish_sku: DishSku | None = Relationship(back_populates="order_items")


class OrderStatusLog(SQLModel, table=True):
    __tablename__ = "order_status_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="customer_order.id", nullable=False, ondelete="CASCADE", index=True
    )
    from_status: OrderStatus | None = Field(default=None, sa_type=String(32))
    to_status: OrderStatus = Field(sa_type=String(32))
    event: str = Field(max_length=64)
    actor: str = Field(max_length=32)
    reason: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, sa_type=String(128), index=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    order: Order | None = Relationship(back_populates="status_logs")


class PaymentRecord(SQLModel, table=True):
    __tablename__ = "payment_record"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="customer_order.id", nullable=False, ondelete="CASCADE", index=True
    )
    provider: str = Field(max_length=32)
    out_trade_no: str = Field(sa_type=String(64), unique=True, index=True)
    amount: Decimal = Field(sa_type=Numeric(10, 2))
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, sa_type=String(32))
    paid_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    order: Order | None = Relationship(back_populates="payments")


class PaymentCallbackLog(SQLModel, table=True):
    __tablename__ = "payment_callback_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(max_length=32, index=True)
    transaction_id: str = Field(max_length=128, index=True)
    payload: str
    signature: str | None = Field(default=None, max_length=255)
    processed: bool = Field(default=False, index=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
