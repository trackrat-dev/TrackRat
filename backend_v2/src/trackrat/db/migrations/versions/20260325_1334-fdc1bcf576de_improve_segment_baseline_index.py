"""Improve segment_transit_times baseline index for congestion queries.

The historical_baseline CTE in congestion.py filters on (data_source,
hour_of_day, day_of_week) then scans departure_time for the 30-day range.
The existing idx_segment_baseline has from_station_code in position 2,
which is a GROUP BY column not a WHERE filter, forcing extra scanning.

Replace with (data_source, hour_of_day, day_of_week, departure_time) to
match the actual query predicate order and eliminate unnecessary scans
for high-volume providers like SUBWAY.

Revision ID: fdc1bcf576de
Revises: 4ae83310c010
Create Date: 2026-03-25T13:34:00Z

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "fdc1bcf576de"
down_revision = "4ae83310c010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_segment_baseline", table_name="segment_transit_times")
    op.create_index(
        "idx_segment_baseline",
        "segment_transit_times",
        ["data_source", "hour_of_day", "day_of_week", "departure_time"],
    )


def downgrade() -> None:
    op.drop_index("idx_segment_baseline", table_name="segment_transit_times")
    op.create_index(
        "idx_segment_baseline",
        "segment_transit_times",
        ["data_source", "from_station_code", "hour_of_day", "departure_time"],
    )
