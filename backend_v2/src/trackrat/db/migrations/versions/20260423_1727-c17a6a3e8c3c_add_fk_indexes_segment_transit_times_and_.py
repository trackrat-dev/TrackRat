"""Add FK indexes on segment_transit_times.journey_id and station_dwell_times.journey_id.

These tables lack indexes on their journey_id foreign key, causing sequential scans
when SQLAlchemy selectinload fetches related records for train detail/departure endpoints.

Revision ID: c17a6a3e8c3c
Revises: 6feb0d5b5600
Create Date: 2026-04-23T17:27:00Z

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c17a6a3e8c3c"
down_revision = "6feb0d5b5600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_segment_journey",
        "segment_transit_times",
        ["journey_id"],
        unique=False,
    )
    op.create_index(
        "idx_dwell_journey",
        "station_dwell_times",
        ["journey_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_dwell_journey", table_name="station_dwell_times")
    op.drop_index("idx_segment_journey", table_name="segment_transit_times")
