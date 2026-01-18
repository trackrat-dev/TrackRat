"""expand live_activity_tokens train_number for PATH

Revision ID: 8e9d270f3461
Revises: 185b07f360c8
Create Date: 2026-01-18 15:32:57.635614

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e9d270f3461'
down_revision = '185b07f360c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Expand train_number column to support PATH train IDs."""
    op.alter_column(
        'live_activity_tokens',
        'train_number',
        type_=sa.String(30),
        existing_type=sa.String(10),
        existing_nullable=False
    )


def downgrade() -> None:
    """Revert column size (may truncate data if PATH IDs exist)."""
    op.alter_column(
        'live_activity_tokens',
        'train_number',
        type_=sa.String(10),
        existing_type=sa.String(30),
        existing_nullable=False
    )