"""add_track_notified_at

Revision ID: 5a14a873c3f9
Revises: b8ca879ae8c5
Create Date: 2026-03-23 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5a14a873c3f9"
down_revision = "b8ca879ae8c5"
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
