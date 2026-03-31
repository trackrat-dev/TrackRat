"""increase_station_code_fields_to_10_for_lirr_mnr

Revision ID: 02527b3a3bcf
Revises: a9ba71e83f54
Create Date: 2026-02-06 13:49:52.943351

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "02527b3a3bcf"
down_revision = "a9ba71e83f54"
branch_labels = None
depends_on = None

# All station_code columns that need widening from VARCHAR(3) to VARCHAR(10)
# to support MNR M-prefix codes (4 chars, e.g. MHRR, M125) and LIRR codes (e.g. LSBK)
COLUMNS_TO_WIDEN = [
    ("train_journeys", "origin_station_code", False),
    ("train_journeys", "terminal_station_code", False),
    ("train_journeys", "discovery_station_code", True),
    ("journey_stops", "station_code", False),
    ("segment_transit_times", "from_station_code", False),
    ("segment_transit_times", "to_station_code", False),
    ("station_dwell_times", "station_code", False),
    ("journey_progress", "last_departed_station", True),
    ("journey_progress", "next_station", True),
    ("live_activity_tokens", "origin_code", False),
    ("live_activity_tokens", "destination_code", False),
    ("gtfs_stop_times", "station_code", True),
]


def _get_existing_tables() -> set[str]:
    """Get the set of tables that actually exist in the database."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    """Widen station code columns from VARCHAR(3) to VARCHAR(10) for LIRR/MNR support."""
    existing = _get_existing_tables()
    for table, column, nullable in COLUMNS_TO_WIDEN:
        if table not in existing:
            continue
        op.alter_column(
            table,
            column,
            existing_type=sa.VARCHAR(length=3),
            type_=sa.VARCHAR(length=10),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    """Revert station code columns from VARCHAR(10) back to VARCHAR(3)."""
    existing = _get_existing_tables()
    for table, column, nullable in COLUMNS_TO_WIDEN:
        if table not in existing:
            continue
        op.alter_column(
            table,
            column,
            existing_type=sa.VARCHAR(length=10),
            type_=sa.VARCHAR(length=3),
            existing_nullable=nullable,
        )
