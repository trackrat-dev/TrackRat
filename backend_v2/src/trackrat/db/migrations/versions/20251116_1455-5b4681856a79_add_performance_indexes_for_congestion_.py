"""add_performance_indexes_for_congestion_api

Revision ID: 5b4681856a79
Revises: 7f9960a4f7c3
Create Date: 2025-11-16 14:55:42.029052

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b4681856a79"
down_revision = "7f9960a4f7c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add composite index on train_journeys for congestion queries
    # This optimizes: WHERE last_updated_at >= cutoff AND is_cancelled = false AND data_source = ?
    op.create_index(
        "idx_congestion_journey_lookup",
        "train_journeys",
        ["last_updated_at", "is_cancelled", "data_source"],
        unique=False,
        postgresql_concurrently=True,
    )

    # Add covering index on journey_stops for consecutive stop joins
    # This optimizes the self-join: js1.journey_id = js2.journey_id AND js2.stop_sequence = js1.stop_sequence + 1
    # Using postgresql_include for columns only needed in SELECT, not WHERE
    op.create_index(
        "idx_journey_stops_sequence_lookup",
        "journey_stops",
        ["journey_id", "stop_sequence", "station_code"],
        unique=False,
        postgresql_concurrently=True,
        postgresql_include=[
            "scheduled_departure",
            "scheduled_arrival",
            "actual_departure",
            "actual_arrival",
        ],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_journey_stops_sequence_lookup", table_name="journey_stops")
    op.drop_index("idx_congestion_journey_lookup", table_name="train_journeys")
