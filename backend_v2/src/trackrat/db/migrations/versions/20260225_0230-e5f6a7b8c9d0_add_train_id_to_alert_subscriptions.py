"""add_train_id_to_alert_subscriptions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-25 02:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add train_id and weekdays_only columns, update check constraint."""
    # Add new columns
    op.add_column(
        "route_alert_subscriptions",
        sa.Column("train_id", sa.String(30), nullable=True),
    )
    op.add_column(
        "route_alert_subscriptions",
        sa.Column(
            "weekdays_only",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Replace the check constraint to include train_id as a third option
    op.drop_constraint("ck_alert_sub_type", "route_alert_subscriptions", type_="check")
    op.create_check_constraint(
        "ck_alert_sub_type",
        "route_alert_subscriptions",
        "(line_id IS NOT NULL) OR "
        "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL) OR "
        "(train_id IS NOT NULL)",
    )

    # Add index for train_id lookups
    op.create_index(
        "idx_alert_sub_train",
        "route_alert_subscriptions",
        ["data_source", "train_id"],
    )


def downgrade() -> None:
    """Remove train_id and weekdays_only columns, restore original constraint."""
    op.drop_index("idx_alert_sub_train", table_name="route_alert_subscriptions")

    op.drop_constraint("ck_alert_sub_type", "route_alert_subscriptions", type_="check")
    op.create_check_constraint(
        "ck_alert_sub_type",
        "route_alert_subscriptions",
        "(line_id IS NOT NULL) OR "
        "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL)",
    )

    op.drop_column("route_alert_subscriptions", "weekdays_only")
    op.drop_column("route_alert_subscriptions", "train_id")
