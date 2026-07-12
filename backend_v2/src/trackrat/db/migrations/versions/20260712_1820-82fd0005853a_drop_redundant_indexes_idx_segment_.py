"""drop redundant indexes idx_segment_lookup idx_stop_journey_station_seq idx_train_id

Index hygiene follow-up to fd85e7f3abb3, from a production index review on
2026-07-12 (pg_stat_user_indexes lifetime counters, never reset; sizes are
current on-disk totals across partitions):

  - idx_segment_lookup (from_station_code, to_station_code, data_source,
    departure_time): 1.22 GB, 8,764 scans — vs 30M on idx_segment_journey.
    Its original consumers (congestion/history baselines) moved to
    idx_segment_baseline in b8ca879ae8c5 because this index lacks
    hour_of_day. The one remaining query shape that could touch it
    (routes.py route-history: from_station_code = ANY + data_source +
    departure_time range) cannot use the to_station_code column in position
    2 anyway, so it degrades to the same leading-column prefix scan that
    idx_recent_segments (from_station_code, to_station_code, created_at)
    already provides.

  - idx_stop_journey_station_seq (journey_id, station_code, stop_sequence):
    847 MB, 86M scans — but every observed query shape is a
    (journey_id, station_code) equality lookup from the collectors'
    stop-merge paths, and unique_journey_stop
    (journey_id, station_code, journey_date) has the identical leading
    prefix, so the planner switches to it at the same cost. Not a *strict*
    prefix (third column differs), which is why the fd85e7f3abb3 sweep
    missed it. journey_id-ordered scans that also need stop_sequence are
    served by idx_journey_stops_sequence_lookup
    (journey_id, stop_sequence, station_code) INCLUDE (...).

  - idx_train_id (train_id): 29 MB — strict leading-column prefix of
    unique_train_journey (train_id, journey_date, data_source); exactly the
    pattern fd85e7f3abb3 dropped elsewhere but missed here.

Together ~2.1 GB (~12% of the database) plus one fewer index to maintain on
each of the two churniest tables (journey_stops writes go from 7 index
updates to 6).

journey_stops and segment_transit_times are partitioned (03db10760b28);
dropping the parent partitioned index cascades to every child partition in
one catalog-only statement. DROP INDEX takes a brief ACCESS EXCLUSIVE lock
on the table, but migrations run at app startup before the scheduler and
API begin issuing queries, so there is no lock queue to stall behind.
DROP/CREATE use IF [NOT] EXISTS so re-runs and hand-applied environments
are no-ops.

Revision ID: 82fd0005853a
Revises: 03db10760b28
Create Date: 2026-07-12 18:20:55.067159

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "82fd0005853a"
down_revision = "03db10760b28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.execute("DROP INDEX IF EXISTS idx_segment_lookup")
    op.execute("DROP INDEX IF EXISTS idx_stop_journey_station_seq")
    op.execute("DROP INDEX IF EXISTS idx_train_id")


def downgrade() -> None:
    """Revert migration."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_segment_lookup ON segment_transit_times "
        "(from_station_code, to_station_code, data_source, departure_time)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_stop_journey_station_seq ON journey_stops "
        "(journey_id, station_code, stop_sequence)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_train_id ON train_journeys (train_id)")
