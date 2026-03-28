"""Widen gtfs_trips.train_id for new transit provider compatibility.

MBTA GTFS feed has trip_short_name values exceeding 20 characters
(e.g., "CR-Weekday-Fall-24-516"), causing StringDataRightTruncationError
during import. This cascades into gtfs_static_no_active_services warnings
since trip data fails to load.

Follows the same pattern as 04c75a8cc919 which widened route_short_name
and station_code for the same reason.

Revision ID: 4a7ab30b2020
Revises: 04c75a8cc919
Create Date: 2026-03-28T01:15:00Z

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4a7ab30b2020"
down_revision = "04c75a8cc919"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "gtfs_trips",
        "train_id",
        type_=sa.String(50),
        existing_type=sa.String(20),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "gtfs_trips",
        "train_id",
        type_=sa.String(20),
        existing_type=sa.String(50),
        existing_nullable=True,
    )
