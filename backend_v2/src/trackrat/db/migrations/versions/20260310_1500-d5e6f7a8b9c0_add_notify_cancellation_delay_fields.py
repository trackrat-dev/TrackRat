"""add_notify_cancellation_delay_fields

Revision ID: d5e6f7a8b9c0
Revises: d4e5f6a7b8ca
Create Date: 2026-03-10 15:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "d4e5f6a7b8ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add per-type alert toggles: notify_cancellation and notify_delay."""
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "notify_cancellation",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "notify_delay",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    """Remove per-type alert toggles."""
    op.drop_column("route_alert_subscriptions", "notify_delay")
    op.drop_column("route_alert_subscriptions", "notify_cancellation")
