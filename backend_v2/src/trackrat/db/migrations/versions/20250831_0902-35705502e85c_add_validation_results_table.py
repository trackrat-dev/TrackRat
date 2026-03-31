"""add_validation_results_table

Revision ID: 35705502e85c
Revises: 6f98f8469447
Create Date: 2025-08-31 09:02:50.095400

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "35705502e85c"
down_revision = "6f98f8469447"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Create validation_results table
    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("route", sa.String(10), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("transit_train_count", sa.Integer(), nullable=False),
        sa.Column("api_train_count", sa.Integer(), nullable=False),
        sa.Column("coverage_percent", sa.Float(), nullable=False),
        sa.Column("missing_trains", sa.JSON(), nullable=True),
        sa.Column("extra_trains", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient queries
    op.create_index(
        "idx_validation_time", "validation_results", ["run_at", "route", "source"]
    )
    op.create_index(
        "idx_validation_coverage",
        "validation_results",
        ["route", "source", "coverage_percent"],
    )


def downgrade() -> None:
    """Revert migration."""
    # Drop indexes
    op.drop_index("idx_validation_coverage", table_name="validation_results")
    op.drop_index("idx_validation_time", table_name="validation_results")

    # Drop table
    op.drop_table("validation_results")
