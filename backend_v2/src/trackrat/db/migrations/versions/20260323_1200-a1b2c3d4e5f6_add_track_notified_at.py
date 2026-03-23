"""add_track_notified_at

Revision ID: a1b2c3d4e5f6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-23 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add track_notified_at to live_activity_tokens."""
    op.add_column(
        "live_activity_tokens",
        sa.Column("track_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove track_notified_at from live_activity_tokens."""
    op.drop_column("live_activity_tokens", "track_notified_at")
