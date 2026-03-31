"""Expand line_code columns to 10 chars for PATH support

Revision ID: b9b7f01aa94d
Revises: f3111b597e88
Create Date: 2026-01-19 15:18:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b9b7f01aa94d"
down_revision = "f3111b597e88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Expand line_code from VARCHAR(2) to VARCHAR(10).

    PATH line codes are up to 7 characters (e.g., NWK-WTC, HOB-33).
    Using 10 for future flexibility.
    """
    op.alter_column(
        "segment_transit_times",
        "line_code",
        type_=sa.String(10),
        existing_type=sa.String(2),
        existing_nullable=True,
    )
    op.alter_column(
        "station_dwell_times",
        "line_code",
        type_=sa.String(10),
        existing_type=sa.String(2),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert line_code to VARCHAR(2)."""
    op.alter_column(
        "segment_transit_times",
        "line_code",
        type_=sa.String(2),
        existing_type=sa.String(10),
        existing_nullable=True,
    )
    op.alter_column(
        "station_dwell_times",
        "line_code",
        type_=sa.String(2),
        existing_type=sa.String(10),
        existing_nullable=True,
    )
