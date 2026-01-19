"""Increase segment_transit_times station_code columns to 3 chars

Revision ID: f3111b597e88
Revises: 8e9d270f3461
Create Date: 2026-01-19 08:23:48.455282

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3111b597e88'
down_revision = '8e9d270f3461'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration.

    PATH station codes are 3 characters (e.g., P33, PJS, PWC) while
    NJT codes are 2 characters. Expand columns to accommodate both.
    """
    op.alter_column(
        'segment_transit_times',
        'from_station_code',
        type_=sa.String(3),
        existing_type=sa.String(2),
        existing_nullable=False
    )
    op.alter_column(
        'segment_transit_times',
        'to_station_code',
        type_=sa.String(3),
        existing_type=sa.String(2),
        existing_nullable=False
    )


def downgrade() -> None:
    """Revert migration."""
    op.alter_column(
        'segment_transit_times',
        'from_station_code',
        type_=sa.String(2),
        existing_type=sa.String(3),
        existing_nullable=False
    )
    op.alter_column(
        'segment_transit_times',
        'to_station_code',
        type_=sa.String(2),
        existing_type=sa.String(3),
        existing_nullable=False
    )