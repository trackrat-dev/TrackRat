"""add_departure_source_column

Revision ID: 11dc95145b34
Revises: 6c8093b3dab2
Create Date: 2025-08-25 08:17:08.730951

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "11dc95145b34"
down_revision = "6c8093b3dab2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add departure_source column to journey_stops table
    # This tracks how we determined that a stop has departed:
    # - 'api_explicit': NJT API returned DEPARTED="YES"
    # - 'sequential_inference': A later stop has departed, so this one must have too
    # - 'time_inference': Train scheduled departure is >5 minutes in the past
    # - NULL: Not yet departed
    op.add_column(
        "journey_stops",
        sa.Column("departure_source", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("journey_stops", "departure_source")
