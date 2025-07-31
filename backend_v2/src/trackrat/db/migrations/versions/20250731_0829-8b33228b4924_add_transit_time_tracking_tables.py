"""add transit time tracking tables

Revision ID: 8b33228b4924
Revises: add_updated_times_and_raw_status_fields
Create Date: 2025-07-31 08:29:35.911167

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b33228b4924"
down_revision = "add_updated_times_and_raw_status_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Create segment_transit_times table
    op.create_table(
        "segment_transit_times",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "journey_id",
            sa.Integer(),
            sa.ForeignKey("train_journeys.id"),
            nullable=False,
        ),
        sa.Column("from_station_code", sa.String(2), nullable=False),
        sa.Column("to_station_code", sa.String(2), nullable=False),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("line_code", sa.String(2)),
        # Timing data
        sa.Column("scheduled_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_minutes", sa.Integer(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        # Context for analysis
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hour_of_day", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for segment_transit_times
    op.create_index(
        "idx_segment_lookup",
        "segment_transit_times",
        ["from_station_code", "to_station_code", "data_source", "departure_time"],
    )
    op.create_index(
        "idx_recent_segments",
        "segment_transit_times",
        ["from_station_code", "to_station_code", "created_at"],
    )

    # Create station_dwell_times table
    op.create_table(
        "station_dwell_times",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "journey_id",
            sa.Integer(),
            sa.ForeignKey("train_journeys.id"),
            nullable=False,
        ),
        sa.Column("station_code", sa.String(2), nullable=False),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("line_code", sa.String(2)),
        # Timing data
        sa.Column("scheduled_minutes", sa.Integer()),
        sa.Column("actual_minutes", sa.Integer(), nullable=False),
        sa.Column("excess_dwell_minutes", sa.Integer(), nullable=False),
        # Station type flags
        sa.Column("is_origin", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_terminal", sa.Boolean(), default=False, nullable=False),
        # Context
        sa.Column("arrival_time", sa.DateTime(timezone=True)),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hour_of_day", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for station_dwell_times
    op.create_index(
        "idx_station_dwell",
        "station_dwell_times",
        ["station_code", "data_source", "departure_time"],
    )
    op.create_index(
        "idx_recent_dwell", "station_dwell_times", ["station_code", "created_at"]
    )

    # Create journey_progress table
    op.create_table(
        "journey_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "journey_id",
            sa.Integer(),
            sa.ForeignKey("train_journeys.id"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Current position
        sa.Column("last_departed_station", sa.String(2)),
        sa.Column("next_station", sa.String(2)),
        # Progress metrics
        sa.Column("stops_completed", sa.Integer(), nullable=False),
        sa.Column("stops_total", sa.Integer(), nullable=False),
        sa.Column("journey_percent", sa.Float(), nullable=False),
        # Delay tracking
        sa.Column("initial_delay_minutes", sa.Integer(), default=0, nullable=False),
        sa.Column("cumulative_transit_delay", sa.Integer(), default=0, nullable=False),
        sa.Column("cumulative_dwell_delay", sa.Integer(), default=0, nullable=False),
        sa.Column("total_delay_minutes", sa.Integer(), nullable=False),
        # Predictions (when available)
        sa.Column("predicted_arrival", sa.DateTime(timezone=True)),
        sa.Column("prediction_confidence", sa.Float()),
        sa.Column("prediction_based_on", sa.Text()),  # JSON array of train_ids
    )

    # Create index for journey_progress
    op.create_index(
        "idx_journey_progress", "journey_progress", ["journey_id", "captured_at"]
    )


def downgrade() -> None:
    """Revert migration."""
    # Drop indexes
    op.drop_index("idx_journey_progress", "journey_progress")
    op.drop_index("idx_recent_dwell", "station_dwell_times")
    op.drop_index("idx_station_dwell", "station_dwell_times")
    op.drop_index("idx_recent_segments", "segment_transit_times")
    op.drop_index("idx_segment_lookup", "segment_transit_times")

    # Drop tables
    op.drop_table("journey_progress")
    op.drop_table("station_dwell_times")
    op.drop_table("segment_transit_times")
