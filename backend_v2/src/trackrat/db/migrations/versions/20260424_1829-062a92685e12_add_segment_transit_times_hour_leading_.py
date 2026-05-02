"""add segment_transit_times hour-leading index for congestion baseline

Revision ID: 062a92685e12
Revises: 4c71508e8fa2
Create Date: 2026-04-24 18:29:20.761458

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "062a92685e12"
down_revision = "4c71508e8fa2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Serves the congestion historical_baseline CTE when data_source is unbound
    # (the web "all" path). idx_segment_baseline leads with data_source, so it
    # can only serve the single-source path. See issue #989.
    #
    # Not using CONCURRENTLY to match project convention (see 5b4681856a79).
    # Migrations run during container startup before the API/collectors are
    # serving traffic, so the brief ACCESS EXCLUSIVE lock is acceptable.
    op.create_index(
        "idx_segment_hour_baseline",
        "segment_transit_times",
        ["hour_of_day", "day_of_week", "departure_time"],
        unique=False,
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_segment_hour_baseline", table_name="segment_transit_times")
