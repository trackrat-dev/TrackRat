"""Widen gtfs_routes.route_short_name from varchar(20) to varchar(50).

MBTA GTFS feed has route_short_name values that exceed 20 characters,
causing StringDataRightTruncationError during GTFS import.

Revision ID: a1b2c3d4e5f6
Revises: fdc1bcf576de
Create Date: 2026-03-27T23:36:00Z

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fdc1bcf576de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "gtfs_routes",
        "route_short_name",
        type_=sa.String(50),
        existing_type=sa.String(20),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "gtfs_routes",
        "route_short_name",
        type_=sa.String(20),
        existing_type=sa.String(50),
        existing_nullable=True,
    )
