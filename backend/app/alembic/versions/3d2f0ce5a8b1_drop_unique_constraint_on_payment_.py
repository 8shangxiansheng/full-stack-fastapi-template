"""Drop unique constraint on payment callback logs

Revision ID: 3d2f0ce5a8b1
Revises: 7f6b5d0e2a11
Create Date: 2026-03-03 20:40:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3d2f0ce5a8b1"
down_revision = "7f6b5d0e2a11"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "uq_payment_callback_log_provider_transaction",
        "payment_callback_log",
        type_="unique",
    )


def downgrade():
    op.create_unique_constraint(
        "uq_payment_callback_log_provider_transaction",
        "payment_callback_log",
        ["provider", "transaction_id"],
    )
