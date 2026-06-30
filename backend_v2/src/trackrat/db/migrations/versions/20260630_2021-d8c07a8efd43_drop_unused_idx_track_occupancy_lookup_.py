"""drop unused idx_track_occupancy_lookup and tune autovacuum

Drops idx_track_occupancy_lookup on journey_stops. It was created to serve
track_occupancy.py, but that query filters station_code + a 2-hour
scheduled_departure window, which the planner satisfies with idx_station_times
(station_code, scheduled_departure) and cheap post-filters. The middle
has_departed_station column (queried as IS NOT TRUE, a non-equality) makes this
index strictly worse than idx_station_times for the query, so it is never
chosen — pg_stat_user_indexes shows 0 scans against a backdrop of billions on
production. A prior cleanup (d170389c0848) deferred dropping it on the theory
that the 0 scans came from stale planner stats; two months of fresh stats with
still-zero scans disproves that, and the index had bloated to ~4 GB.

Also lowers the autovacuum scale factors on the three high-churn journey tables
so dead tuples (and the index bloat they cause) are reclaimed at ~2% turnover
instead of the 20% default, which on multi-million-row tables let bloat grow
for too long between vacuums.

Revision ID: d8c07a8efd43
Revises: 896c9fb11394
Create Date: 2026-06-30 20:21:45.083464

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d8c07a8efd43"
down_revision = "896c9fb11394"
branch_labels = None
depends_on = None


# Tables whose autovacuum thresholds we tighten. They are UPDATE-heavy during
# collection (times, track, flags churn through each train's life), so the
# 20% default scale factor lets bloat accumulate before autovacuum fires.
_CHURN_TABLES = ("journey_stops", "segment_transit_times", "train_journeys")


def upgrade() -> None:
    """Apply migration."""
    # IF EXISTS so this is a no-op if the index was already dropped manually
    # (e.g. via DROP INDEX CONCURRENTLY during an emergency disk reclaim).
    op.execute("DROP INDEX IF EXISTS idx_track_occupancy_lookup")

    for table in _CHURN_TABLES:
        op.execute(
            f"ALTER TABLE {table} SET ("
            "autovacuum_vacuum_scale_factor = 0.02, "
            "autovacuum_analyze_scale_factor = 0.02"
            ")"
        )


def downgrade() -> None:
    """Revert migration."""
    for table in _CHURN_TABLES:
        op.execute(
            f"ALTER TABLE {table} RESET ("
            "autovacuum_vacuum_scale_factor, "
            "autovacuum_analyze_scale_factor"
            ")"
        )

    op.create_index(
        "idx_track_occupancy_lookup",
        "journey_stops",
        ["station_code", "has_departed_station", "scheduled_departure"],
        unique=False,
    )
