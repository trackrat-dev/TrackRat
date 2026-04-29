"""add data_source to live_activity_tokens

Revision ID: 896c9fb11394
Revises: 062a92685e12
Create Date: 2026-04-29 12:26:57.009719

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "896c9fb11394"
down_revision = "062a92685e12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration.

    Adds data_source to live_activity_tokens so the push-update scheduler can
    disambiguate train_journeys when a train_id is shared across transit
    systems (e.g. NJT and Amtrak both running 1989 today). Nullable: tokens
    registered by older iOS clients that don't send data_source must keep
    working.
    """
    op.add_column(
        "live_activity_tokens",
        sa.Column("data_source", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("live_activity_tokens", "data_source")
