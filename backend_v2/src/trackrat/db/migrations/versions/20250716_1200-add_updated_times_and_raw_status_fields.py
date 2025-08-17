"""add_updated_times_and_raw_status_fields

Revision ID: updated_times_raw_status
Revises: 900093cd1ced
Create Date: 2025-07-16 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "updated_times_raw_status"
down_revision = "900093cd1ced"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to journey_stops table
    op.add_column(
        "journey_stops",
        sa.Column("updated_arrival", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "journey_stops",
        sa.Column("updated_departure", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "journey_stops", sa.Column("raw_amtrak_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "journey_stops",
        sa.Column("raw_njt_departed_flag", sa.String(10), nullable=True),
    )
    op.add_column(
        "journey_stops",
        sa.Column(
            "has_departed_station", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # Remove old fields that are no longer needed
    op.drop_column("journey_stops", "departed")
    op.drop_column("journey_stops", "status")
    op.drop_column("journey_stops", "status_details")


def downgrade() -> None:
    # Add back old fields
    op.add_column(
        "journey_stops",
        sa.Column("departed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("journey_stops", sa.Column("status", sa.String(20), nullable=True))
    op.add_column(
        "journey_stops", sa.Column("status_details", sa.JSON(), nullable=True)
    )

    # Remove new fields
    op.drop_column("journey_stops", "has_departed_station")
    op.drop_column("journey_stops", "raw_njt_departed_flag")
    op.drop_column("journey_stops", "raw_amtrak_status")
    op.drop_column("journey_stops", "updated_departure")
    op.drop_column("journey_stops", "updated_arrival")
