"""add_chat_messages_and_admin_devices

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-10 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add chat_messages and admin_devices tables for developer chat."""
    op.create_table(
        "admin_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("sender_role", sa.String(5), nullable=False),
        sa.Column("message", sa.String(255), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["device_tokens.device_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "sender_role IN ('user', 'admin')",
            name="ck_chat_sender_role",
        ),
    )

    op.create_index("idx_chat_device_id", "chat_messages", ["device_id"])
    op.create_index(
        "idx_chat_created_at", "chat_messages", ["device_id", "created_at"]
    )
    op.create_index(
        "idx_chat_unread",
        "chat_messages",
        ["device_id", "sender_role", "read_at"],
    )


def downgrade() -> None:
    """Remove chat tables."""
    op.drop_index("idx_chat_unread", table_name="chat_messages")
    op.drop_index("idx_chat_created_at", table_name="chat_messages")
    op.drop_index("idx_chat_device_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("admin_devices")
