"""Widen GTFS column sizes for MBTA compatibility.

1. gtfs_routes.route_short_name: varchar(20) -> varchar(50)
   MBTA GTFS feed has route_short_name values exceeding 20 characters,
   causing StringDataRightTruncationError during import.

2. gtfs_stop_times.station_code: varchar(3) -> varchar(10)
   Model defines String(10) but migration created String(3). MBTA and other
   providers have station codes longer than 3 characters.

Revision ID: 04c75a8cc919
Revises: fdc1bcf576de
Create Date: 2026-03-27T23:36:00Z

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "04c75a8cc919"
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
    op.alter_column(
        "gtfs_stop_times",
        "station_code",
        type_=sa.String(10),
        existing_type=sa.String(3),
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
    op.alter_column(
        "gtfs_stop_times",
        "station_code",
        type_=sa.String(3),
        existing_type=sa.String(10),
        existing_nullable=True,
    )
