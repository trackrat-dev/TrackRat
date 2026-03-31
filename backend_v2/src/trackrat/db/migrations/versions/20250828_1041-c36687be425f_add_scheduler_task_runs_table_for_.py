"""Add scheduler_task_runs table for horizontal scaling

Revision ID: c36687be425f
Revises: 89bfc05ebfac
Create Date: 2025-08-28 10:41:48.065202

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c36687be425f"
down_revision = "89bfc05ebfac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Create scheduler_task_runs table for tracking task execution across replicas
    op.create_table(
        "scheduler_task_runs",
        sa.Column("task_name", sa.String(50), nullable=False),
        sa.Column("last_successful_run", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, default=0),
        sa.Column("average_duration_ms", sa.Integer(), nullable=True),
        sa.Column("last_duration_ms", sa.Integer(), nullable=True),
        sa.Column("last_instance_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("task_name"),
    )

    # Create index for efficient freshness checks
    op.create_index(
        "idx_task_freshness",
        "scheduler_task_runs",
        ["task_name", "last_successful_run"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_task_freshness", table_name="scheduler_task_runs")
    op.drop_table("scheduler_task_runs")
