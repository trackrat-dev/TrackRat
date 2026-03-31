"""add_service_alerts_and_planned_work

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-10 12:02:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add service_alerts table and planned work columns to subscriptions."""
    # New table for MTA service alerts
    op.create_table(
        "service_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.String(100), nullable=False),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("alert_type", sa.String(20), nullable=False),
        sa.Column("affected_route_ids", sa.JSON(), nullable=False),
        sa.Column("header_text", sa.Text(), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("active_periods", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "data_source", name="uq_service_alert_id"),
    )
    op.create_index(
        "idx_service_alert_active", "service_alerts", ["is_active", "data_source"]
    )
    op.create_index(
        "idx_service_alert_type", "service_alerts", ["alert_type", "data_source"]
    )

    # Add planned work opt-in to route alert subscriptions
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "include_planned_work",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Add service alert dedup tracking
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("last_service_alert_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove service alerts table and planned work columns."""
    op.drop_column("route_alert_subscriptions", "last_service_alert_ids")
    op.drop_column("route_alert_subscriptions", "include_planned_work")
    op.drop_index("idx_service_alert_type", table_name="service_alerts")
    op.drop_index("idx_service_alert_active", table_name="service_alerts")
    op.drop_table("service_alerts")
