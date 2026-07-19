"""widen data_source columns to varchar(20) for SEPTA_METRO

Revision ID: 600992355efa
Revises: 82fd0005853a
Create Date: 2026-07-18 20:09:12.606674

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "600992355efa"
down_revision = "82fd0005853a"
branch_labels = None
depends_on = None


# Tables whose data_source column was String(10); SEPTA_METRO (11 chars) needs 20.
# Widening a varchar is a metadata-only change in Postgres (no table rewrite),
# so this is instant even on the large/partitioned tables.
_TABLES = (
    "train_journeys",
    "route_alert_subscriptions",
    "service_alerts",
    "segment_transit_times",
    "station_dwell_times",
    "gtfs_feed_info",
    "gtfs_routes",
    "gtfs_trips",
    "gtfs_calendar",
    "gtfs_calendar_dates",
)


def upgrade() -> None:
    """Widen data_source columns from varchar(10) to varchar(20)."""
    for table in _TABLES:
        op.alter_column(
            table,
            "data_source",
            type_=sa.String(length=20),
            existing_type=sa.String(length=10),
        )
    # validation_results uses "source" for the same NJT/AMTRAK-style value.
    op.alter_column(
        "validation_results",
        "source",
        type_=sa.String(length=20),
        existing_type=sa.String(length=10),
    )


def downgrade() -> None:
    """Revert data_source columns to varchar(10)."""
    for table in _TABLES:
        op.alter_column(
            table,
            "data_source",
            type_=sa.String(length=10),
            existing_type=sa.String(length=20),
        )
    op.alter_column(
        "validation_results",
        "source",
        type_=sa.String(length=10),
        existing_type=sa.String(length=20),
    )
