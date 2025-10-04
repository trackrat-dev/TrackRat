"""add journey_progress table

Revision ID: 7f9960a4f7c3
Revises: ae677490d55c
Create Date: 2025-09-27 12:20:47.904374

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7f9960a4f7c3"
down_revision = "ae677490d55c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "journey_progress" not in inspector.get_table_names():
        op.create_table(
            "journey_progress",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("journey_id", sa.Integer(), nullable=False),
            sa.Column(
                "captured_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("last_departed_station", sa.String(length=3), nullable=True),
            sa.Column("next_station", sa.String(length=3), nullable=True),
            sa.Column("stops_completed", sa.Integer(), nullable=False),
            sa.Column("stops_total", sa.Integer(), nullable=False),
            sa.Column("journey_percent", sa.Float(), nullable=False),
            sa.Column(
                "initial_delay_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "cumulative_transit_delay",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "cumulative_dwell_delay",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("total_delay_minutes", sa.Integer(), nullable=False),
            sa.Column("predicted_arrival", sa.DateTime(timezone=True), nullable=True),
            sa.Column("prediction_confidence", sa.Float(), nullable=True),
            sa.Column("prediction_based_on", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["journey_id"],
                ["train_journeys.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_journey_progress",
            "journey_progress",
            ["journey_id", "captured_at"],
            unique=False,
        )


def downgrade() -> None:
    """Revert migration."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "journey_progress" in inspector.get_table_names():
        op.drop_index("idx_journey_progress", table_name="journey_progress")
        op.drop_table("journey_progress")
