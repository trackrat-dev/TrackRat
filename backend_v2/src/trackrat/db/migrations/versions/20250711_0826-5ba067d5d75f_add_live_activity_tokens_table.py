"""add_live_activity_tokens_table

Revision ID: 5ba067d5d75f
Revises: add_data_source
Create Date: 2025-07-11 08:26:49.941634

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5ba067d5d75f"
down_revision = "add_data_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "live_activity_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("push_token", sa.String(), nullable=False),
        sa.Column("activity_id", sa.String(), nullable=False),
        sa.Column("train_number", sa.String(10), nullable=False),
        sa.Column("origin_code", sa.String(2), nullable=False),
        sa.Column("destination_code", sa.String(2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("push_token"),
    )
    op.create_index(
        "idx_active_tokens", "live_activity_tokens", ["is_active", "train_number"]
    )
    op.create_index("idx_token_expiry", "live_activity_tokens", ["expires_at"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_token_expiry", table_name="live_activity_tokens")
    op.drop_index("idx_active_tokens", table_name="live_activity_tokens")
    op.drop_table("live_activity_tokens")
