"""add_journey_stop_route_history_index

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-02-24 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_stop_journey_station_seq",
        "journey_stops",
        ["journey_id", "station_code", "stop_sequence"],
    )


def downgrade() -> None:
    op.drop_index("idx_stop_journey_station_seq", table_name="journey_stops")
