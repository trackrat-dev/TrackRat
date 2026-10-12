"""add last_registered_at to device_tokens

Revision ID: 3cb8b7a54aa2
Revises: e3921513ad63
Create Date: 2026-10-11 21:16:26.770631

Records when a device last called /devices/register so registrations that are
never pushed to (no alert subscriptions, so no APNS 410 ever prunes them) can be
swept once stale (issue #1858).

Existing rows are deliberately backfilled to the migration time, not from
updated_at: updated_at only moves when the APNS token changes, and tokens are
stable for months, so it would mark daily users as long-gone and the first
sweep would delete their server-only route preferences. The cost is that the
pre-existing backlog is swept one retention window after deploy, not at once.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3cb8b7a54aa2"
down_revision = "e3921513ad63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add device_tokens.last_registered_at, backfilled to now()."""
    op.add_column(
        "device_tokens",
        sa.Column(
            "last_registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove device_tokens.last_registered_at."""
    op.drop_column("device_tokens", "last_registered_at")
