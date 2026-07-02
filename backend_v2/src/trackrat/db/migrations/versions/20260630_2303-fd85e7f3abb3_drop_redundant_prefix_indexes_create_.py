"""drop redundant prefix indexes, create idx_delay_forecaster, autovacuum throughput

Index hygiene follow-up to d8c07a8efd43. Reconciles the model with production
and removes redundant indexes that only added write amplification (and therefore
bloat) on the two churniest tables.

Drops three indexes, each a strict leading-column prefix of a wider index that
already serves the same predicates:
  - idx_journey_date (journey_date)        -> idx_journey_date_source (journey_date, data_source)
  - idx_journey_sequence (journey_id, stop_sequence)
        -> idx_journey_stops_sequence_lookup (journey_id, stop_sequence, station_code)
  - idx_last_updated (last_updated_at)
        -> idx_congestion_journey_lookup (last_updated_at, is_cancelled, data_source)

Creates idx_delay_forecaster, which the model has always declared but no
migration ever created, so production has been missing it. Its query
(delay_forecaster._get_train_id_stats: train_id + origin_station_code +
data_source + journey_date >= cutoff) matches the index exactly, and all four
columns are static so it does not bloat from last_updated_at churn.

Also raises autovacuum_vacuum_cost_limit on the three high-churn tables so the
(now more frequent, per d8c07a8efd43) autovacuums have the I/O budget to keep
pace instead of falling behind and letting bloat accumulate.

DROP/CREATE use IF [NOT] EXISTS so this is a no-op for objects already changed
by hand on production (e.g. via DROP/CREATE INDEX CONCURRENTLY during reclaim).

Revision ID: fd85e7f3abb3
Revises: d8c07a8efd43
Create Date: 2026-06-30 23:03:16.997321

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "fd85e7f3abb3"
down_revision = "d8c07a8efd43"
branch_labels = None
depends_on = None


_CHURN_TABLES = ("journey_stops", "segment_transit_times", "train_journeys")


def upgrade() -> None:
    """Apply migration."""
    # Create the index the model has always declared but prod never had.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delay_forecaster ON train_journeys "
        "(train_id, origin_station_code, data_source, journey_date)"
    )

    # Drop redundant prefix indexes (superseded by wider indexes above).
    op.execute("DROP INDEX IF EXISTS idx_journey_date")
    op.execute("DROP INDEX IF EXISTS idx_journey_sequence")
    op.execute("DROP INDEX IF EXISTS idx_last_updated")

    for table in _CHURN_TABLES:
        op.execute(f"ALTER TABLE {table} SET (autovacuum_vacuum_cost_limit = 1000)")


def downgrade() -> None:
    """Revert migration."""
    for table in _CHURN_TABLES:
        op.execute(f"ALTER TABLE {table} RESET (autovacuum_vacuum_cost_limit)")

    op.create_index("idx_journey_date", "train_journeys", ["journey_date"])
    op.create_index(
        "idx_journey_sequence", "journey_stops", ["journey_id", "stop_sequence"]
    )
    op.create_index("idx_last_updated", "train_journeys", ["last_updated_at"])

    op.execute("DROP INDEX IF EXISTS idx_delay_forecaster")
