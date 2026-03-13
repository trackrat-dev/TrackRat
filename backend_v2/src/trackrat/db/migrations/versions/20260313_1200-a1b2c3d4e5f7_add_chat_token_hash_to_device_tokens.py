"""add_chat_token_hash_to_device_tokens

Revision ID: a1b2c3d4e5f7
Revises: f7a8b9c0d1e2
Create Date: 2026-03-13 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_tokens",
        sa.Column("chat_token_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("device_tokens", "chat_token_hash")
