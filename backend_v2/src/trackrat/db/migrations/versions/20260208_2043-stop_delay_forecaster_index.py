"""add_stop_delay_forecaster_index

Add composite index on journey_stops(station_code, journey_id) to optimize
stop-level delay forecaster queries that join journey_stops to train_journeys.

Revision ID: 8a3f1c2d4e5b
Revises: 02527b3a3bcf
Create Date: 2026-02-08 20:43:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8a3f1c2d4e5b"
down_revision = "02527b3a3bcf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_stop_delay_forecaster",
        "journey_stops",
        ["station_code", "journey_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_stop_delay_forecaster", table_name="journey_stops")
