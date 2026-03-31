"""Add discovery track fields to train journeys

Revision ID: 900093cd1ced
Revises: 0b0e39be5e16
Create Date: 2025-07-13 08:28:05.950813

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "900093cd1ced"
down_revision = "0b0e39be5e16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add discovery track fields to train_journeys table
    op.add_column(
        "train_journeys", sa.Column("discovery_track", sa.String(5), nullable=True)
    )
    op.add_column(
        "train_journeys",
        sa.Column("discovery_station_code", sa.String(2), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    # Remove discovery track fields from train_journeys table
    op.drop_column("train_journeys", "discovery_station_code")
    op.drop_column("train_journeys", "discovery_track")
