"""Add route_preferences table for per-device route filter settings.

Revision ID: f9a8b7c6d5e4
Revises: 8771778d5ae1
Create Date: 2026-03-17 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "f9a8b7c6d5e4"
down_revision = "8771778d5ae1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("from_station_code", sa.String(10), nullable=False),
        sa.Column("to_station_code", sa.String(10), nullable=False),
        sa.Column(
            "enabled_systems",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
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
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["device_tokens.device_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "from_station_code",
            "to_station_code",
            name="uq_route_pref_device_stations",
        ),
    )
    op.create_index("idx_route_pref_device", "route_preferences", ["device_id"])


def downgrade() -> None:
    op.drop_index("idx_route_pref_device", table_name="route_preferences")
    op.drop_table("route_preferences")
