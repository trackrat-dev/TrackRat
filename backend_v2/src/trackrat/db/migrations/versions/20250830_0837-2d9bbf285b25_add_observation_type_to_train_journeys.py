"""add_observation_type_to_train_journeys

Revision ID: 2d9bbf285b25
Revises: c36687be425f
Create Date: 2025-08-30 08:37:48.789603

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2d9bbf285b25"
down_revision = "c36687be425f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add observation_type column to track if data is from schedule or real-time
    op.add_column(
        "train_journeys",
        sa.Column(
            "observation_type",
            sa.String(10),
            nullable=False,
            server_default="OBSERVED",
            comment="SCHEDULED for schedule API data, OBSERVED for real-time data",
        ),
    )

    # Create index for efficient filtering by observation type
    op.create_index(
        "idx_train_journey_observation",
        "train_journeys",
        ["journey_date", "observation_type"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_train_journey_observation", table_name="train_journeys")
    op.drop_column("train_journeys", "observation_type")
