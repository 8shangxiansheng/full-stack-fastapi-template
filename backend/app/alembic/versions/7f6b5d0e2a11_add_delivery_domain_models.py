"""Add delivery domain models

Revision ID: 7f6b5d0e2a11
Revises: fe56fa70289e
Create Date: 2026-03-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7f6b5d0e2a11"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_category_name", "category", ["name"], unique=False)

    op.create_table(
        "dish",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dish_name", "dish", ["name"], unique=False)

    op.create_table(
        "dish_sku",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cart",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cart_user_id", "cart", ["user_id"], unique=True)

    op.create_table(
        "cart_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dish_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cart_id"], ["cart.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dish_sku_id"], ["dish_sku.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cart_item_cart_id", "cart_item", ["cart_id"], unique=False)
    op.create_index("ix_cart_item_dish_sku_id", "cart_item", ["dish_sku_id"], unique=False)

    op.create_table(
        "address",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receiver_name", sa.String(length=255), nullable=False),
        sa.Column("receiver_phone", sa.String(length=32), nullable=False),
        sa.Column("province", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_address_user_id", "address", ["user_id"], unique=False)

    op.create_table(
        "customer_order",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["address_id"], ["address.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_order_order_no", "customer_order", ["order_no"], unique=True)
    op.create_index("ix_customer_order_status", "customer_order", ["status"], unique=False)
    op.create_index("ix_customer_order_user_id", "customer_order", ["user_id"], unique=False)

    op.create_table(
        "order_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dish_sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dish_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("sku_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dish_sku_id"], ["dish_sku.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_item_order_id", "order_item", ["order_id"], unique=False)

    op.create_table(
        "order_status_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_status_log_order_id", "order_status_log", ["order_id"], unique=False)
    op.create_index(
        "ix_order_status_log_idempotency_key",
        "order_status_log",
        ["idempotency_key"],
        unique=False,
    )

    op.create_table(
        "payment_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("out_trade_no", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_record_order_id", "payment_record", ["order_id"], unique=False)
    op.create_index(
        "ix_payment_record_out_trade_no",
        "payment_record",
        ["out_trade_no"],
        unique=True,
    )

    op.create_table(
        "payment_callback_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("transaction_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("signature", sa.String(length=255), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "transaction_id",
            name="uq_payment_callback_log_provider_transaction",
        ),
    )
    op.create_index(
        "ix_payment_callback_log_provider", "payment_callback_log", ["provider"], unique=False
    )
    op.create_index(
        "ix_payment_callback_log_transaction_id",
        "payment_callback_log",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_callback_log_processed", "payment_callback_log", ["processed"], unique=False
    )


def downgrade():
    op.drop_index("ix_payment_callback_log_processed", table_name="payment_callback_log")
    op.drop_index("ix_payment_callback_log_transaction_id", table_name="payment_callback_log")
    op.drop_index("ix_payment_callback_log_provider", table_name="payment_callback_log")
    op.drop_table("payment_callback_log")

    op.drop_index("ix_payment_record_out_trade_no", table_name="payment_record")
    op.drop_index("ix_payment_record_order_id", table_name="payment_record")
    op.drop_table("payment_record")

    op.drop_index("ix_order_status_log_idempotency_key", table_name="order_status_log")
    op.drop_index("ix_order_status_log_order_id", table_name="order_status_log")
    op.drop_table("order_status_log")

    op.drop_index("ix_order_item_order_id", table_name="order_item")
    op.drop_table("order_item")

    op.drop_index("ix_customer_order_user_id", table_name="customer_order")
    op.drop_index("ix_customer_order_status", table_name="customer_order")
    op.drop_index("ix_customer_order_order_no", table_name="customer_order")
    op.drop_table("customer_order")

    op.drop_index("ix_address_user_id", table_name="address")
    op.drop_table("address")

    op.drop_index("ix_cart_item_dish_sku_id", table_name="cart_item")
    op.drop_index("ix_cart_item_cart_id", table_name="cart_item")
    op.drop_table("cart_item")

    op.drop_index("ix_cart_user_id", table_name="cart")
    op.drop_table("cart")

    op.drop_table("dish_sku")

    op.drop_index("ix_dish_name", table_name="dish")
    op.drop_table("dish")

    op.drop_index("ix_category_name", table_name="category")
    op.drop_table("category")
