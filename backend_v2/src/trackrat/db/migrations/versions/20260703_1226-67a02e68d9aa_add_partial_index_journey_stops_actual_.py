"""add_partial_index_journey_stops_actual_departure

Fixes issue #1354: routes/summary (scope=train and scope=route on cache
miss) times out because the "actual_departure if present, else
scheduled_departure" window filter in summary.py has no usable index on
the actual_departure branch. idx_station_times only covers
scheduled_departure, so Postgres picks whichever station_code-prefixed
index is cheapest (usually idx_stop_track_distribution) and filters the
rest by hand.

Confirmed via EXPLAIN ANALYZE on the two reported hot paths:
- PATH PWC->PNK: 109.7s, scanned 315,607 rows via idx_stop_track_distribution
  to return 63.
- WMATA A01->B04: 26.3s, 1.6M rows rechecked via a lossy bitmap scan on the
  same index, to return 107.

Partial (WHERE actual_departure IS NOT NULL) since most journey_stops rows
never populate it until the stop is actually observed departing, keeping
this meaningfully smaller than a full index — and unlike the
has_departed_station-keyed index dropped in d8c07a8efd43, actual_departure
is written once and not repeatedly toggled, so it shouldn't bloat the same
way.

IMPORTANT: journey_stops is a 35M+ row, high-churn table (see
d8c07a8efd43 / fd85e7f3abb3). A plain CREATE INDEX here would hold a lock
for the full build — the same failure mode that got the arrival_source
backfill migration (f7a8b9c0d1e2) pulled for causing MIG health-check
failures. Before deploying this migration to any loaded environment
(staging or production), build the index by hand first:

    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stop_actual_departure
    ON journey_stops (station_code, actual_departure)
    WHERE actual_departure IS NOT NULL;

Once that's done, `alembic upgrade head` here is an instant no-op
reconciliation (IF NOT EXISTS). On a fresh/empty database (dev, CI) the
op.execute below just creates it directly since there's no contention.

Revision ID: 67a02e68d9aa
Revises: fd85e7f3abb3
Create Date: 2026-07-03 12:26:40.832432

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "67a02e68d9aa"
down_revision = "fd85e7f3abb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_stop_actual_departure ON journey_stops "
        "(station_code, actual_departure) WHERE actual_departure IS NOT NULL"
    )


def downgrade() -> None:
    """Revert migration."""
    op.execute("DROP INDEX IF EXISTS idx_stop_actual_departure")
