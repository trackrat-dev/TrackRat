"""Remove API calls table

Revision ID: remove_api_calls
Revises: 019443de01cd
Create Date: 2025-07-05 00:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "remove_api_calls"
down_revision = "019443de01cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove API calls table and index."""
    # Drop the index first
    op.drop_index("idx_api_calls", table_name="api_calls")

    # Drop the table
    op.drop_table("api_calls")


def downgrade() -> None:
    """Recreate API calls table and index."""
    # Recreate the table
    op.create_table(
        "api_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=50), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("cached", sa.Boolean(), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate the index
    op.create_index(
        "idx_api_calls", "api_calls", ["endpoint", "called_at"], unique=False
    )
