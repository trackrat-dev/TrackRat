"""Widen line_code columns from varchar(10) to varchar(15).

Metra UP-NW line code is "METRA-UP-NW" (11 chars), causing
StringDataRightTruncationError and silently dropping all UP-NW trains.

Affects three tables: train_journeys, segment_transit_times, station_dwell_times.

Revision ID: 6feb0d5b5600
Revises: 4a7ab30b2020
Create Date: 2026-04-04T15:28:00Z

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6feb0d5b5600"
down_revision = "4a7ab30b2020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "train_journeys",
        "line_code",
        existing_type=sa.String(10),
        type_=sa.String(15),
        existing_nullable=False,
    )
    op.alter_column(
        "segment_transit_times",
        "line_code",
        existing_type=sa.String(10),
        type_=sa.String(15),
        existing_nullable=True,
    )
    op.alter_column(
        "station_dwell_times",
        "line_code",
        existing_type=sa.String(10),
        type_=sa.String(15),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "train_journeys",
        "line_code",
        existing_type=sa.String(15),
        type_=sa.String(10),
        existing_nullable=False,
    )
    op.alter_column(
        "segment_transit_times",
        "line_code",
        existing_type=sa.String(15),
        type_=sa.String(10),
        existing_nullable=True,
    )
    op.alter_column(
        "station_dwell_times",
        "line_code",
        existing_type=sa.String(15),
        type_=sa.String(10),
        existing_nullable=True,
    )
