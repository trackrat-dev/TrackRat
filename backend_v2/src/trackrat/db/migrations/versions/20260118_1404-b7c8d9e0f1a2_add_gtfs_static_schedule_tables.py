"""Add GTFS static schedule tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-18 14:04:00.000000

Adds tables for storing GTFS static schedule data:
- gtfs_feed_info: Track feed download status and rate limiting
- gtfs_routes: Route definitions
- gtfs_trips: Trip definitions with service patterns
- gtfs_stop_times: Stop times for each trip
- gtfs_calendar: Weekly service patterns
- gtfs_calendar_dates: Service exceptions
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Create gtfs_feed_info table
    op.create_table(
        "gtfs_feed_info",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(10), nullable=False, unique=True),
        sa.Column("feed_url", sa.String(500), nullable=False),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_parse_at", sa.DateTime(timezone=True)),
        sa.Column("feed_start_date", sa.Date),
        sa.Column("feed_end_date", sa.Date),
        sa.Column("route_count", sa.Integer),
        sa.Column("trip_count", sa.Integer),
        sa.Column("stop_time_count", sa.Integer),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("idx_gtfs_feed_source", "gtfs_feed_info", ["data_source"])

    # Create gtfs_routes table
    op.create_table(
        "gtfs_routes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("route_id", sa.String(50), nullable=False),
        sa.Column("route_short_name", sa.String(20)),
        sa.Column("route_long_name", sa.String(200)),
        sa.Column("route_color", sa.String(6)),
    )
    op.create_unique_constraint(
        "uq_gtfs_route", "gtfs_routes", ["data_source", "route_id"]
    )
    op.create_index("idx_gtfs_route_lookup", "gtfs_routes", ["data_source", "route_id"])

    # Create gtfs_trips table
    op.create_table(
        "gtfs_trips",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("trip_id", sa.String(100), nullable=False),
        sa.Column(
            "route_id", sa.Integer, sa.ForeignKey("gtfs_routes.id"), nullable=False
        ),
        sa.Column("service_id", sa.String(50), nullable=False),
        sa.Column("trip_headsign", sa.String(100)),
        sa.Column("train_id", sa.String(20)),
        sa.Column("direction_id", sa.Integer),
    )
    op.create_unique_constraint(
        "uq_gtfs_trip", "gtfs_trips", ["data_source", "trip_id"]
    )
    op.create_index(
        "idx_gtfs_trip_service", "gtfs_trips", ["data_source", "service_id"]
    )
    op.create_index("idx_gtfs_trip_lookup", "gtfs_trips", ["data_source", "trip_id"])

    # Create gtfs_stop_times table
    op.create_table(
        "gtfs_stop_times",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "trip_id", sa.Integer, sa.ForeignKey("gtfs_trips.id"), nullable=False
        ),
        sa.Column("stop_sequence", sa.Integer, nullable=False),
        sa.Column("gtfs_stop_id", sa.String(50), nullable=False),
        sa.Column("station_code", sa.String(3)),
        sa.Column("arrival_time", sa.String(8)),
        sa.Column("departure_time", sa.String(8)),
        sa.Column("pickup_type", sa.Integer, default=0),
        sa.Column("drop_off_type", sa.Integer, default=0),
    )
    op.create_index(
        "idx_gtfs_stop_time_trip", "gtfs_stop_times", ["trip_id", "stop_sequence"]
    )
    op.create_index(
        "idx_gtfs_stop_time_station",
        "gtfs_stop_times",
        ["station_code", "departure_time"],
    )

    # Create gtfs_calendar table
    op.create_table(
        "gtfs_calendar",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("service_id", sa.String(50), nullable=False),
        sa.Column("monday", sa.Boolean, nullable=False, default=False),
        sa.Column("tuesday", sa.Boolean, nullable=False, default=False),
        sa.Column("wednesday", sa.Boolean, nullable=False, default=False),
        sa.Column("thursday", sa.Boolean, nullable=False, default=False),
        sa.Column("friday", sa.Boolean, nullable=False, default=False),
        sa.Column("saturday", sa.Boolean, nullable=False, default=False),
        sa.Column("sunday", sa.Boolean, nullable=False, default=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
    )
    op.create_unique_constraint(
        "uq_gtfs_calendar", "gtfs_calendar", ["data_source", "service_id"]
    )
    op.create_index(
        "idx_gtfs_calendar_dates",
        "gtfs_calendar",
        ["data_source", "start_date", "end_date"],
    )

    # Create gtfs_calendar_dates table
    op.create_table(
        "gtfs_calendar_dates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("service_id", sa.String(50), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("exception_type", sa.Integer, nullable=False),
    )
    op.create_unique_constraint(
        "uq_gtfs_calendar_date",
        "gtfs_calendar_dates",
        ["data_source", "service_id", "date"],
    )
    op.create_index(
        "idx_gtfs_calendar_date_lookup", "gtfs_calendar_dates", ["data_source", "date"]
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_table("gtfs_calendar_dates")
    op.drop_table("gtfs_calendar")
    op.drop_table("gtfs_stop_times")
    op.drop_table("gtfs_trips")
    op.drop_table("gtfs_routes")
    op.drop_table("gtfs_feed_info")
