"""add_direction_to_alert_subscriptions

Revision ID: f4a5b6c7d8e9
Revises: e5f6a7b8c9d0
Create Date: 2026-03-01 16:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f4a5b6c7d8e9"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add direction column for directional line subscriptions."""
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("direction", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    """Remove direction column."""
    op.drop_column("route_alert_subscriptions", "direction")
