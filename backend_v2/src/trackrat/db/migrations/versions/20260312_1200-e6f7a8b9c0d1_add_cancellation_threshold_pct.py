"""add_cancellation_threshold_pct

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-12 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cancellation_threshold_pct to route_alert_subscriptions."""
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("cancellation_threshold_pct", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove cancellation_threshold_pct from route_alert_subscriptions."""
    op.drop_column("route_alert_subscriptions", "cancellation_threshold_pct")
