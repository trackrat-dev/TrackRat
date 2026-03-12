"""backfill_arrival_source_for_existing_stops

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-12 17:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill arrival_source for stops written before the column was added.

    The arrival_source column was added in d4e5f6a7b8ca but without a data
    backfill. Stops with actual_arrival data but NULL arrival_source are
    excluded from OTP calculations, causing routes to report NULL on-time
    percentage despite having hundreds of trains with arrival data.
    """
    # Batch 1: Stops on completed journeys where actual != scheduled
    # (strong signal these were API-observed arrivals)
    op.execute("""
        UPDATE journey_stops js
        SET arrival_source = 'api_observed'
        FROM train_journeys tj
        WHERE tj.id = js.journey_id
          AND js.arrival_source IS NULL
          AND js.actual_arrival IS NOT NULL
          AND js.scheduled_arrival IS NOT NULL
          AND js.actual_arrival != js.scheduled_arrival
        """)

    # Batch 2: Stops on completed journeys where actual == scheduled
    # (could be scheduled_fallback or exact on-time, but on a completed
    # journey we trust the data)
    op.execute("""
        UPDATE journey_stops js
        SET arrival_source = 'api_observed'
        FROM train_journeys tj
        WHERE tj.id = js.journey_id
          AND js.arrival_source IS NULL
          AND js.actual_arrival IS NOT NULL
          AND tj.is_completed = true
        """)

    # Batch 3: Remaining stops with actual_arrival on non-completed journeys
    # where actual == scheduled. These are departed intermediate stops.
    op.execute("""
        UPDATE journey_stops
        SET arrival_source = 'api_observed'
        WHERE arrival_source IS NULL
          AND actual_arrival IS NOT NULL
          AND has_departed_station = true
        """)


def downgrade() -> None:
    """Clear backfilled arrival_source values.

    Note: This cannot distinguish between backfilled and newly-written values,
    so it clears all arrival_source. This is safe because the column was
    recently added and a full re-collection will repopulate it.
    """
    op.execute("""
        UPDATE journey_stops
        SET arrival_source = NULL
        WHERE arrival_source IS NOT NULL
        """)
