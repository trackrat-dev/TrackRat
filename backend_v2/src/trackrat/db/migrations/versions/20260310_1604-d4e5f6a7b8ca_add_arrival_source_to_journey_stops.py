"""add_arrival_source_to_journey_stops

Revision ID: d4e5f6a7b8ca
Revises: c3d4e5f6a7b8
Create Date: 2026-03-10 16:04:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8ca"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add arrival_source column to journey_stops for OTP accuracy."""
    op.add_column(
        "journey_stops",
        sa.Column("arrival_source", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    """Remove arrival_source column from journey_stops."""
    op.drop_column("journey_stops", "arrival_source")
