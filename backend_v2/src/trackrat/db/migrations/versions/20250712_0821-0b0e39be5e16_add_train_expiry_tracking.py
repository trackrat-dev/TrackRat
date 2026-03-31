"""add_train_expiry_tracking

Revision ID: 0b0e39be5e16
Revises: 5ba067d5d75f
Create Date: 2025-07-12 08:21:29.812923

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0b0e39be5e16"
down_revision = "5ba067d5d75f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add api_error_count column
    op.add_column(
        "train_journeys",
        sa.Column("api_error_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Add is_expired column
    op.add_column(
        "train_journeys",
        sa.Column("is_expired", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Create index for efficient queries on active journeys
    op.create_index(
        "idx_active_journeys",
        "train_journeys",
        ["is_completed", "is_expired", "is_cancelled"],
        unique=False,
    )


def downgrade() -> None:
    """Revert migration."""
    # Drop index
    op.drop_index("idx_active_journeys", table_name="train_journeys")

    # Drop columns
    op.drop_column("train_journeys", "is_expired")
    op.drop_column("train_journeys", "api_error_count")
