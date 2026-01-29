"""Add cancellation_reason column to train_journeys

Revision ID: a1b2c3d4e5f6
Revises: b9b7f01aa94d
Create Date: 2026-01-29 01:43:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "b9b7f01aa94d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cancellation_reason column for storing NJT cancellation explanations."""
    op.add_column(
        "train_journeys",
        sa.Column("cancellation_reason", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    """Remove cancellation_reason column."""
    op.drop_column("train_journeys", "cancellation_reason")
