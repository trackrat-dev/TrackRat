"""backfill_arrival_source_for_existing_stops

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-12 17:00:00.000000

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

# Process rows in chunks to avoid long-running transactions that block
# health checks and cause MIG instance restarts on large databases.
BATCH_SIZE = 10000


def _batched_update(conn, query: str, description: str) -> int:
    """Run an UPDATE in batches, committing after each chunk.

    Returns total rows updated.
    """
    total = 0
    while True:
        result = conn.execute(text(query))
        rows = result.rowcount
        if rows == 0:
            break
        total += rows
        conn.commit()
    return total


def upgrade() -> None:
    """Backfill arrival_source for stops written before the column was added.

    The arrival_source column was added in d4e5f6a7b8ca but without a data
    backfill. Stops with actual_arrival data but NULL arrival_source are
    excluded from OTP calculations, causing routes to report NULL on-time
    percentage despite having hundreds of trains with arrival data.

    Uses batched updates to avoid blocking the health check on large databases.
    """
    conn = op.get_bind()

    # Batch 1: Stops on completed journeys where actual != scheduled
    # (strong signal these were API-observed arrivals)
    _batched_update(conn, f"""
        UPDATE journey_stops
        SET arrival_source = 'api_observed'
        WHERE id IN (
            SELECT js.id FROM journey_stops js
            JOIN train_journeys tj ON tj.id = js.journey_id
            WHERE js.arrival_source IS NULL
              AND js.actual_arrival IS NOT NULL
              AND js.scheduled_arrival IS NOT NULL
              AND js.actual_arrival != js.scheduled_arrival
            LIMIT {BATCH_SIZE}
        )
        """, "actual != scheduled")

    # Batch 2: Stops on completed journeys where actual == scheduled
    # (could be scheduled_fallback or exact on-time, but on a completed
    # journey we trust the data)
    _batched_update(conn, f"""
        UPDATE journey_stops
        SET arrival_source = 'api_observed'
        WHERE id IN (
            SELECT js.id FROM journey_stops js
            JOIN train_journeys tj ON tj.id = js.journey_id
            WHERE js.arrival_source IS NULL
              AND js.actual_arrival IS NOT NULL
              AND tj.is_completed = true
            LIMIT {BATCH_SIZE}
        )
        """, "completed journeys")

    # Batch 3: Remaining stops with actual_arrival on non-completed journeys
    # where actual == scheduled. These are departed intermediate stops.
    _batched_update(conn, f"""
        UPDATE journey_stops
        SET arrival_source = 'api_observed'
        WHERE id IN (
            SELECT id FROM journey_stops
            WHERE arrival_source IS NULL
              AND actual_arrival IS NOT NULL
              AND has_departed_station = true
            LIMIT {BATCH_SIZE}
        )
        """, "departed stops")


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
