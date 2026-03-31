"""Add data_source field to train_journeys

Revision ID: add_data_source
Revises: remove_api_calls
Create Date: 2025-07-05 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_data_source"
down_revision = "cfecb8a3db76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add data_source field and update constraints."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("train_journeys", schema=None) as batch_op:
        # Add the data_source column
        batch_op.add_column(
            sa.Column(
                "data_source",
                sa.String(length=10),
                nullable=False,
                server_default="NJT",
            )
        )

        # Drop the old unique constraint
        batch_op.drop_constraint("unique_train_journey", type_="unique")

        # Create new unique constraint that includes data_source
        batch_op.create_unique_constraint(
            "unique_train_journey", ["train_id", "journey_date", "data_source"]
        )

        # Add index on data_source
        batch_op.create_index("idx_data_source", ["data_source"])


def downgrade() -> None:
    """Remove data_source field and revert constraints."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("train_journeys", schema=None) as batch_op:
        # Drop the new unique constraint
        batch_op.drop_constraint("unique_train_journey", type_="unique")

        # Drop the data_source index
        batch_op.drop_index("idx_data_source")

        # Drop the data_source column
        batch_op.drop_column("data_source")

        # Recreate the old unique constraint
        batch_op.create_unique_constraint(
            "unique_train_journey", ["train_id", "journey_date"]
        )
