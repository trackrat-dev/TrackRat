"""add_device_tokens_and_alert_subscriptions

Revision ID: c7d8e9f0a1b2
Revises: 8a3f1c2d4e5b
Create Date: 2026-02-22 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "8a3f1c2d4e5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("apns_token", sa.String(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )

    op.create_table(
        "route_alert_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "device_id",
            sa.String(64),
            sa.ForeignKey("device_tokens.device_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data_source", sa.String(10), nullable=False),
        sa.Column("line_id", sa.String(30), nullable=True),
        sa.Column("from_station_code", sa.String(10), nullable=True),
        sa.Column("to_station_code", sa.String(10), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("last_alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_alert_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(line_id IS NOT NULL) OR "
            "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL)",
            name="ck_alert_sub_type",
        ),
    )
    op.create_index(
        "idx_alert_sub_device", "route_alert_subscriptions", ["device_id"]
    )
    op.create_index(
        "idx_alert_sub_line",
        "route_alert_subscriptions",
        ["data_source", "line_id"],
    )
    op.create_index(
        "idx_alert_sub_stations",
        "route_alert_subscriptions",
        ["data_source", "from_station_code", "to_station_code"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_alert_sub_stations", table_name="route_alert_subscriptions")
    op.drop_index("idx_alert_sub_line", table_name="route_alert_subscriptions")
    op.drop_index("idx_alert_sub_device", table_name="route_alert_subscriptions")
    op.drop_table("route_alert_subscriptions")
    op.drop_table("device_tokens")
