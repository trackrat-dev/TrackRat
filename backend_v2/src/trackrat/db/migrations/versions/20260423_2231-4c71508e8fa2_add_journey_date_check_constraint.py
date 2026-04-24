"""Add CHECK constraint on train_journeys.journey_date to prevent data corruption.

Rejects journey dates before 2020-01-01 or more than 365 days in the future.
Triggered by production data corruption where NJT date parsing produced
journey_date=3025-06-22 (year 3025).

Revision ID: 4c71508e8fa2
Revises: d170389c0848
Create Date: 2026-04-23T22:31:17Z
"""

from alembic import op

revision = "4c71508e8fa2"
down_revision = "d170389c0848"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM train_journeys
        WHERE journey_date < '2020-01-01'
           OR journey_date > (CURRENT_DATE + INTERVAL '365 days')
        """
    )
    op.execute(
        """
        ALTER TABLE train_journeys
        ADD CONSTRAINT chk_reasonable_journey_date
        CHECK (
            journey_date >= '2020-01-01'
            AND journey_date <= (CURRENT_DATE + INTERVAL '365 days')
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE train_journeys
        DROP CONSTRAINT IF EXISTS chk_reasonable_journey_date
        """
    )
