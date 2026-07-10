"""drop unused journey_snapshots table

journey_snapshots is write-only: every write site sets
raw_stop_list_data={} and no code anywhere reads from the table
(see issue #1345). Collectors and the model no longer reference it,
so drop it to stop the per-cycle delete-then-insert churn.

Revision ID: b9f37157aada
Revises: 896c9fb11394
Create Date: 2026-07-01 18:16:38.737584

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b9f37157aada"
down_revision = "896c9fb11394"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.drop_table("journey_snapshots")


def downgrade() -> None:
    """Revert migration."""
    op.create_table(
        "journey_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("journey_id", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("raw_stop_list_data", sa.JSON(), nullable=False),
        sa.Column("train_status", sa.String(length=50), nullable=True),
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("completed_stops", sa.Integer(), nullable=True),
        sa.Column("total_stops", sa.Integer(), nullable=True),
        sa.Column("track_assignments", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["journey_id"],
            ["train_journeys.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_journey_time",
        "journey_snapshots",
        ["journey_id", "captured_at"],
        unique=False,
    )
