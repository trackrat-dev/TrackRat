"""Allow system-wide alert subscriptions.

Relaxes the ck_alert_sub_type check constraint to permit subscriptions
where all of line_id, from_station_code, to_station_code, and train_id
are NULL, representing a system-wide subscription keyed only by data_source.

Revision ID: 4ae83310c010
Revises: b8ca879ae8c5
Create Date: 2026-03-24 16:44:00.000000+00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "4ae83310c010"
down_revision = "b8ca879ae8c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old constraint and add the relaxed one
    op.drop_constraint("ck_alert_sub_type", "route_alert_subscriptions", type_="check")
    op.create_check_constraint(
        "ck_alert_sub_type",
        "route_alert_subscriptions",
        "(line_id IS NOT NULL) OR "
        "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL) OR "
        "(train_id IS NOT NULL) OR "
        "(line_id IS NULL AND from_station_code IS NULL AND to_station_code IS NULL AND train_id IS NULL)",
    )
    # Index for system-wide subscriptions (data_source only, all identifiers NULL)
    op.create_index(
        "idx_alert_sub_system_wide",
        "route_alert_subscriptions",
        ["data_source"],
        postgresql_where="line_id IS NULL AND from_station_code IS NULL AND to_station_code IS NULL AND train_id IS NULL",
    )


def downgrade() -> None:
    op.drop_index("idx_alert_sub_system_wide", table_name="route_alert_subscriptions")
    op.drop_constraint("ck_alert_sub_type", "route_alert_subscriptions", type_="check")
    op.create_check_constraint(
        "ck_alert_sub_type",
        "route_alert_subscriptions",
        "(line_id IS NOT NULL) OR "
        "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL) OR "
        "(train_id IS NOT NULL)",
    )
