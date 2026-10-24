"""widen client train id columns to 64

Revision ID: 74985c32620b
Revises: 3cb8b7a54aa2
Create Date: 2026-10-24 09:04:31.739713

Live Activity registration 500'd for GTFS-scheduled subway trains: their
train_id is the untruncated trip id ("S6-L0S2-6-1091-S01_056500_6..S03R",
34 chars) and live_activity_tokens.train_number was varchar(30) (issue #1928).
route_alert_subscriptions.train_id receives the same client-supplied ids and
is widened alongside it. Widening a varchar is metadata-only in Postgres (no
table rewrite, and the idx_active_tokens index is kept).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "74985c32620b"
down_revision = "3cb8b7a54aa2"
branch_labels = None
depends_on = None

COLUMNS = (
    ("live_activity_tokens", "train_number", False),
    ("route_alert_subscriptions", "train_id", True),
)


def upgrade() -> None:
    """Widen the client-supplied train id columns from varchar(30) to varchar(64)."""
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.String(64),
            existing_type=sa.String(30),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    """Narrow back to varchar(30), truncating any id that no longer fits."""
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.String(30),
            existing_type=sa.String(64),
            existing_nullable=nullable,
            postgresql_using=f"left({column}, 30)",
        )
