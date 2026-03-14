"""add_on_delete_cascade_to_journey_fks

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-14 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

# All child tables of train_journeys that need ON DELETE CASCADE.
# These FK constraints were created without ondelete, which means:
# 1. SQLAlchemy must load all cascade="all, delete-orphan" relationships
#    during flush to check for orphans — triggering greenlet_spawn errors
#    in async context when relationships use lazy="raise_on_sql".
# 2. Direct SQL deletes on train_journeys would fail with FK violations.
_CHILD_TABLES = [
    "journey_stops",
    "journey_snapshots",
    "segment_transit_times",
    "station_dwell_times",
    "journey_progress",
]


def upgrade() -> None:
    """Add ON DELETE CASCADE to all journey_id foreign keys."""
    for table in _CHILD_TABLES:
        constraint_name = f"{table}_journey_id_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table,
            "train_journeys",
            ["journey_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Remove ON DELETE CASCADE from all journey_id foreign keys."""
    for table in _CHILD_TABLES:
        constraint_name = f"{table}_journey_id_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table,
            "train_journeys",
            ["journey_id"],
            ["id"],
        )
