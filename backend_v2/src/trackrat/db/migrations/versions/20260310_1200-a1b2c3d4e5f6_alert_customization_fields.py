"""alert_customization_fields

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-03-10 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace weekdays_only with customizable alert fields."""
    # Add new columns
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "active_days",
            sa.Integer(),
            nullable=False,
            server_default="127",
        ),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("active_start_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("active_end_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("timezone", sa.String(40), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("delay_threshold_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("service_threshold_pct", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "notify_recovery",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("digest_time_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("last_digest_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Migrate weekdays_only=true → active_days=31 (Mon-Fri bitmask)
    op.execute(
        "UPDATE route_alert_subscriptions SET active_days = 31 WHERE weekdays_only = true"
    )

    # Drop old column
    op.drop_column("route_alert_subscriptions", "weekdays_only")


def downgrade() -> None:
    """Restore weekdays_only, remove customization fields."""
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "weekdays_only",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Migrate active_days=31 back to weekdays_only=true
    op.execute(
        "UPDATE route_alert_subscriptions SET weekdays_only = true WHERE active_days = 31"
    )

    op.drop_column("route_alert_subscriptions", "last_digest_at")
    op.drop_column("route_alert_subscriptions", "digest_time_minutes")
    op.drop_column("route_alert_subscriptions", "notify_recovery")
    op.drop_column("route_alert_subscriptions", "service_threshold_pct")
    op.drop_column("route_alert_subscriptions", "delay_threshold_minutes")
    op.drop_column("route_alert_subscriptions", "timezone")
    op.drop_column("route_alert_subscriptions", "active_end_minutes")
    op.drop_column("route_alert_subscriptions", "active_start_minutes")
    op.drop_column("route_alert_subscriptions", "active_days")
