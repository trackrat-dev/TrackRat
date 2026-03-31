"""add_scaling_performance_indexes

Revision ID: a1b2c3d4e5f6
Revises: 5b4681856a79
Create Date: 2025-12-02 10:00:00.000000

Adds composite indexes to optimize queries that degrade as database scales:
- idx_track_occupancy_lookup: Optimizes track occupancy queries
- idx_stop_track_distribution: Optimizes track distribution aggregations
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "5b4681856a79"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add composite index for track occupancy queries
    # Used by track_occupancy.py to find occupied tracks at a station
    # Optimizes: WHERE station_code = ? AND has_departed_station = ? AND scheduled_departure BETWEEN ? AND ?
    op.create_index(
        "idx_track_occupancy_lookup",
        "journey_stops",
        ["station_code", "has_departed_station", "scheduled_departure"],
        unique=False,
    )

    # Add composite index for track distribution queries
    # Used by historical_track_predictor.py for GROUP BY aggregations
    # Optimizes: SELECT track, COUNT(*) FROM journey_stops WHERE station_code = ? GROUP BY track
    op.create_index(
        "idx_stop_track_distribution",
        "journey_stops",
        ["station_code", "track"],
        unique=False,
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_stop_track_distribution", table_name="journey_stops")
    op.drop_index("idx_track_occupancy_lookup", table_name="journey_stops")
