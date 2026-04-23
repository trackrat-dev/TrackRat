"""Drop unused indexes to reclaim ~100MB and speed up writes.

All indexes have idx_scan = 0 in pg_stat_user_indexes on production.
idx_track_occupancy_lookup is excluded despite zero scans because
track_occupancy.py actively queries its column combination; the zero
scans are likely due to stale planner stats from the P0 scheduler leak.

Dropped: idx_captured_at, idx_station_dwell, idx_recent_dwell,
idx_discovery_time, idx_validation_coverage, idx_validation_time,
idx_service_alert_type, idx_alert_sub_line, idx_alert_sub_stations,
idx_task_freshness, idx_gtfs_feed_source.

Revision ID: d170389c0848
Revises: c17a6a3e8c3c
Create Date: 2026-04-23T17:49:00Z

"""

from alembic import op

revision = "d170389c0848"
down_revision = "c17a6a3e8c3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_captured_at", table_name="journey_snapshots")
    op.drop_index("idx_station_dwell", table_name="station_dwell_times")
    op.drop_index("idx_recent_dwell", table_name="station_dwell_times")
    op.drop_index("idx_discovery_time", table_name="discovery_runs")
    op.drop_index("idx_validation_coverage", table_name="validation_results")
    op.drop_index("idx_validation_time", table_name="validation_results")
    op.drop_index("idx_service_alert_type", table_name="service_alerts")
    op.drop_index("idx_alert_sub_line", table_name="route_alert_subscriptions")
    op.drop_index("idx_alert_sub_stations", table_name="route_alert_subscriptions")
    op.drop_index("idx_task_freshness", table_name="scheduler_task_runs")
    op.drop_index("idx_gtfs_feed_source", table_name="gtfs_feed_info")


def downgrade() -> None:
    op.create_index("idx_captured_at", "journey_snapshots", ["captured_at"])
    op.create_index(
        "idx_station_dwell",
        "station_dwell_times",
        ["station_code", "data_source", "departure_time"],
    )
    op.create_index(
        "idx_recent_dwell", "station_dwell_times", ["station_code", "created_at"]
    )
    op.create_index("idx_discovery_time", "discovery_runs", ["station_code", "run_at"])
    op.create_index(
        "idx_validation_coverage",
        "validation_results",
        ["route", "source", "coverage_percent"],
    )
    op.create_index(
        "idx_validation_time", "validation_results", ["run_at", "route", "source"]
    )
    op.create_index(
        "idx_service_alert_type", "service_alerts", ["alert_type", "data_source"]
    )
    op.create_index(
        "idx_alert_sub_line",
        "route_alert_subscriptions",
        ["data_source", "line_id"],
    )
    op.create_index(
        "idx_alert_sub_stations",
        "route_alert_subscriptions",
        ["data_source", "from_station_code", "to_station_code"],
    )
    op.create_index(
        "idx_task_freshness",
        "scheduler_task_runs",
        ["task_name", "last_successful_run"],
    )
    op.create_index("idx_gtfs_feed_source", "gtfs_feed_info", ["data_source"])
