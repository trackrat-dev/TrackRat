"""Add baseline index on segment_transit_times for congestion/history queries.

Both congestion.py and routes.py run baseline calculations that filter by
data_source, from_station_code, hour_of_day, and departure_time. The existing
idx_segment_lookup does not cover hour_of_day, forcing sequential scans on
large tables. This index accelerates those queries.

Revision ID: a1b2c3d4e5f6
Revises: f9a8b7c6d5e4
Create Date: 2026-03-19T14:00:00Z

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f9a8b7c6d5e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_segment_baseline",
        "segment_transit_times",
        ["data_source", "from_station_code", "hour_of_day", "departure_time"],
    )


def downgrade() -> None:
    op.drop_index("idx_segment_baseline", table_name="segment_transit_times")
