"""Add composite index (journey_date, data_source) on train_journeys.

Subway queries that filter by both journey_date and data_source are slow
because PostgreSQL must scan the single-column idx_journey_date and then
heap-filter by data_source. This composite index allows efficient index-only
lookups for these common filter combinations.

Revision ID: 8771778d5ae1
Revises: b8c9d0e1f2a3
Create Date: 2026-03-16T13:56:00Z

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8771778d5ae1"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_journey_date_source",
        "train_journeys",
        ["journey_date", "data_source"],
    )


def downgrade() -> None:
    op.drop_index("idx_journey_date_source", table_name="train_journeys")
