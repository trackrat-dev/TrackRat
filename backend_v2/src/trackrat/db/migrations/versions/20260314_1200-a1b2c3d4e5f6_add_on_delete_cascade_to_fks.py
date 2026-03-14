"""add_on_delete_cascade_to_fks

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-14 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

# All child tables that need ON DELETE CASCADE added to their FK constraints.
# Without this, SQLAlchemy's flush checks orphan status on unloaded
# cascade="all, delete-orphan" relationships, triggering greenlet_spawn
# errors in async context when lazy="raise_on_sql" is set.
# Additionally, direct SQL deletes on parent tables would fail with FK violations.
_JOURNEY_CHILDREN = [
    ("journey_stops", "train_journeys", "journey_id", "id"),
    ("journey_snapshots", "train_journeys", "journey_id", "id"),
    ("segment_transit_times", "train_journeys", "journey_id", "id"),
    ("station_dwell_times", "train_journeys", "journey_id", "id"),
    ("journey_progress", "train_journeys", "journey_id", "id"),
    ("gtfs_trips", "gtfs_routes", "route_id", "id"),
    ("gtfs_stop_times", "gtfs_trips", "trip_id", "id"),
]


def upgrade() -> None:
    """Add ON DELETE CASCADE to all FK constraints that lack it."""
    for child_table, parent_table, fk_col, parent_col in _JOURNEY_CHILDREN:
        constraint_name = f"{child_table}_{fk_col}_fkey"
        op.drop_constraint(constraint_name, child_table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            child_table,
            parent_table,
            [fk_col],
            [parent_col],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Remove ON DELETE CASCADE from FK constraints."""
    for child_table, parent_table, fk_col, parent_col in _JOURNEY_CHILDREN:
        constraint_name = f"{child_table}_{fk_col}_fkey"
        op.drop_constraint(constraint_name, child_table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            child_table,
            parent_table,
            [fk_col],
            [parent_col],
        )
