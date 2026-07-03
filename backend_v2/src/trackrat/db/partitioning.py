"""
Postgres range-partition management for journey_stops and
segment_transit_times (issue #1343).

Both tables are partitioned monthly so retention can `DROP TABLE` a whole
partition instead of relying on `DELETE` + cascade + autovacuum, which marks
tuples dead but never returns space to the filesystem. Partition names follow
`{table}_y{YYYY}_m{MM}` plus one `{table}_default` catch-all partition.

Postgres requires every unique/primary key constraint on a partitioned table
to include the partition key column, and does not auto-create partitions —
callers must keep a rolling window of partitions present ahead of the data
that will land in them. `ensure_future_partitions` (called from
`retention_cleanup` and from the `after_create` DDL event on the ORM models)
handles that; `drop_old_partitions` handles reclaiming old ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PartitionedTable:
    name: str
    partition_column: str
    column_type: str  # "date" or "timestamptz" — affects bound literal formatting


PARTITIONED_TABLES: tuple[PartitionedTable, ...] = (
    PartitionedTable("journey_stops", "journey_date", "date"),
    PartitionedTable("segment_transit_times", "departure_time", "timestamptz"),
)

# How far back/forward of "today" to keep partitions pre-created. NJT schedule
# generation runs ~27 hours ahead and the Amtrak pattern scheduler up to 22
# days ahead, so 2 months of forward buffer comfortably covers both even
# right at a month boundary; 1 month back covers any late-arriving writes for
# journeys that started just before a boundary.
MONTHS_BACK = 1
MONTHS_FORWARD = 2

_PARTITION_NAME_RE = re.compile(
    r"^(?P<table>[a-z_]+)_y(?P<year>\d{4})_m(?P<month>\d{2})$"
)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Add `delta` months to a (year, month) pair (1-indexed month)."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def month_end_exclusive(year: int, month: int) -> date:
    """First day of the following month — the exclusive upper bound."""
    next_year, next_month = _add_months(year, month, 1)
    return date(next_year, next_month, 1)


def partition_name(table: str, year: int, month: int) -> str:
    return f"{table}_y{year:04d}_m{month:02d}"


def default_partition_name(table: str) -> str:
    return f"{table}_default"


def _format_bound(d: date, column_type: str) -> str:
    """Format a date as a partition bound literal.

    timestamptz bounds get an explicit UTC offset so the boundary doesn't
    depend on the creating session's `TimeZone` GUC (Postgres evaluates
    unqualified timestamp literals in FOR VALUES against that setting).
    """
    if column_type == "timestamptz":
        return f"{d.isoformat()} 00:00:00+00"
    return d.isoformat()


def create_partition_sql(pt: PartitionedTable, year: int, month: int) -> str:
    name = partition_name(pt.name, year, month)
    start = _format_bound(month_start(year, month), pt.column_type)
    end = _format_bound(month_end_exclusive(year, month), pt.column_type)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {pt.name} "
        f"FOR VALUES FROM ('{start}') TO ('{end}')"
    )


def create_default_partition_sql(pt: PartitionedTable) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {default_partition_name(pt.name)} "
        f"PARTITION OF {pt.name} DEFAULT"
    )


def rolling_window_sql(
    pt: PartitionedTable,
    reference_date: date,
    months_back: int = MONTHS_BACK,
    months_forward: int = MONTHS_FORWARD,
) -> list[str]:
    """Idempotent SQL statements to ensure the rolling partition window exists."""
    statements = [create_default_partition_sql(pt)]
    for delta in range(-months_back, months_forward + 1):
        year, month = _add_months(reference_date.year, reference_date.month, delta)
        statements.append(create_partition_sql(pt, year, month))
    return statements


def get_partitioned_table(name: str) -> PartitionedTable:
    for pt in PARTITIONED_TABLES:
        if pt.name == name:
            return pt
    raise KeyError(f"{name!r} is not a managed partitioned table")


def initial_setup_sql(reference_date: date) -> list[str]:
    """All SQL needed to bootstrap the rolling partition window for every
    managed table. Used by the Alembic migration, where every managed table
    already exists by the time it runs."""
    statements: list[str] = []
    for pt in PARTITIONED_TABLES:
        statements.extend(rolling_window_sql(pt, reference_date))
    return statements


def ensure_future_partitions_sync(
    conn: Connection, reference_date: date | None = None
) -> None:
    """Sync counterpart for Alembic (sync connection, every managed table
    already exists)."""
    ref = reference_date or date.today()
    for statement in initial_setup_sql(ref):
        conn.execute(text(statement))


def ensure_future_partitions_sync_for_table(
    conn: Connection, pt: PartitionedTable, reference_date: date | None = None
) -> None:
    """Sync partition bootstrap scoped to a single table.

    Used by each model's `after_create` DDL event (backing
    `Base.metadata.create_all()` in tests) — at that point sibling
    partitioned tables may not have been created yet, so bootstrapping
    every managed table from a single table's event would fail.
    """
    ref = reference_date or date.today()
    for statement in rolling_window_sql(pt, ref):
        conn.execute(text(statement))


async def ensure_future_partitions(
    db: AsyncSession, reference_date: date | None = None
) -> None:
    """Top up the rolling partition window for all managed tables. Idempotent —
    safe to call on every retention_cleanup run."""
    ref = reference_date or date.today()
    for statement in initial_setup_sql(ref):
        await db.execute(text(statement))


async def _list_partitions(db: AsyncSession, table: str) -> list[str]:
    result = await db.execute(
        text(
            "SELECT child.relname FROM pg_inherits "
            "JOIN pg_class parent ON pg_inherits.inhparent = parent.oid "
            "JOIN pg_class child ON pg_inherits.inhrelid = child.oid "
            "WHERE parent.relname = :table"
        ),
        {"table": table},
    )
    return [row[0] for row in result]


async def drop_old_partitions(
    db: AsyncSession, cutoff_date: date
) -> dict[str, list[str]]:
    """Drop dated partitions of every managed table whose entire range is
    older than `cutoff_date`. The DEFAULT partition and anything not matching
    the `{table}_y{YYYY}_m{MM}` naming convention is left alone.

    Returns a dict of table name -> dropped partition names (only tables with
    at least one drop are included).
    """
    dropped: dict[str, list[str]] = {}
    for pt in PARTITIONED_TABLES:
        droppable: list[str] = []
        for relname in await _list_partitions(db, pt.name):
            match = _PARTITION_NAME_RE.match(relname)
            if not match or match.group("table") != pt.name:
                continue
            year, month = int(match.group("year")), int(match.group("month"))
            if month_end_exclusive(year, month) <= cutoff_date:
                droppable.append(relname)

        for relname in droppable:
            await db.execute(text(f"DROP TABLE IF EXISTS {relname}"))
            logger.info(
                "partition_dropped",
                table=pt.name,
                partition=relname,
                cutoff_date=str(cutoff_date),
            )

        if droppable:
            dropped[pt.name] = droppable

    return dropped


# ---------------------------------------------------------------------------
# Legacy-table backfill (issue #1343)
#
# Migration 03db10760b28 renames the pre-partition tables to `*_legacy` and
# creates fresh, empty partitioned tables under the original names. It does no
# data movement itself (a full-table scan at startup is what got f7a8b9c0d1e2
# reverted). Instead this backfill runs as a batched background task
# (`SchedulerService.backfill_legacy_partitions`) after the app is up: it
# copies the most recent `retention_days` of rows from each `*_legacy` table
# into the new partitions (newest first, so recent history — route history,
# congestion, segment analytics — becomes readable again fastest), then drops
# each `*_legacy` table once its copy completes, reclaiming the ~33 GB in one
# shot instead of over a 60-day cascade drain.
#
# Progress is tracked in `partition_backfill_state` (created by the migration)
# rather than via ON CONFLICT, because segment_transit_times has no natural
# unique key to dedupe on. We copy by descending legacy `id` and persist the
# lowest id copied so far, so a mid-backfill restart resumes without
# re-copying (and thus without duplicating). Fresh target ids are assigned by
# the new table's own identity/sequence — legacy ids are never preserved, so
# they can't collide with the ids live collectors are already writing.
# ---------------------------------------------------------------------------

BACKFILL_STATE_TABLE = "partition_backfill_state"
BACKFILL_BATCH_SIZE = 10_000
# Batches copied per scheduler invocation, per legacy table. Bounds how long a
# single run holds a connection / how big its transaction gets; the task runs
# on a short interval so the backfill still completes within hours.
BACKFILL_MAX_BATCHES_PER_RUN = 20


@dataclass(frozen=True)
class LegacyBackfill:
    legacy_table: str
    target_table: str
    # SELECT that returns the next batch of legacy ids to copy (newest first),
    # restricted to the retention window. `{cursor}` is filled with either ""
    # (first batch) or the "id < :cursor" guard for resumption.
    select_ids_sql: str
    cursor_clause: str
    # INSERT ... SELECT that copies the chosen legacy ids into the new table.
    insert_sql: str
    # journey_stops filters on train_journeys.journey_date (a DATE); segments
    # filter on their own departure_time (a timestamptz). True => bind the
    # cutoff as a UTC datetime so asyncpg types it correctly for timestamptz.
    cutoff_is_timestamptz: bool


LEGACY_BACKFILLS: tuple[LegacyBackfill, ...] = (
    LegacyBackfill(
        legacy_table="journey_stops_legacy",
        target_table="journey_stops",
        select_ids_sql=(
            "SELECT l.id FROM journey_stops_legacy l "
            "JOIN train_journeys tj ON tj.id = l.journey_id "
            "WHERE tj.journey_date >= :cutoff {cursor} "
            "ORDER BY l.id DESC LIMIT :batch"
        ),
        cursor_clause="AND l.id < :cursor",
        insert_sql=(
            "INSERT INTO journey_stops ("
            "journey_id, journey_date, station_code, station_name, stop_sequence, "
            "scheduled_arrival, scheduled_departure, updated_arrival, "
            "updated_departure, actual_arrival, actual_departure, raw_amtrak_status, "
            "raw_njt_departed_flag, has_departed_station, departure_source, "
            "arrival_source, track, track_assigned_at, pickup_only, dropoff_only, "
            "created_at, updated_at) "
            "SELECT l.journey_id, tj.journey_date, l.station_code, l.station_name, "
            "l.stop_sequence, l.scheduled_arrival, l.scheduled_departure, "
            "l.updated_arrival, l.updated_departure, l.actual_arrival, "
            "l.actual_departure, l.raw_amtrak_status, l.raw_njt_departed_flag, "
            "l.has_departed_station, l.departure_source, l.arrival_source, l.track, "
            "l.track_assigned_at, l.pickup_only, l.dropoff_only, l.created_at, "
            "l.updated_at "
            "FROM journey_stops_legacy l "
            "JOIN train_journeys tj ON tj.id = l.journey_id "
            "WHERE l.id = ANY(:ids)"
        ),
        cutoff_is_timestamptz=False,
    ),
    LegacyBackfill(
        legacy_table="segment_transit_times_legacy",
        target_table="segment_transit_times",
        select_ids_sql=(
            "SELECT id FROM segment_transit_times_legacy "
            "WHERE departure_time >= :cutoff {cursor} "
            "ORDER BY id DESC LIMIT :batch"
        ),
        cursor_clause="AND id < :cursor",
        insert_sql=(
            "INSERT INTO segment_transit_times ("
            "journey_id, from_station_code, to_station_code, data_source, line_code, "
            "scheduled_minutes, actual_minutes, delay_minutes, departure_time, "
            "hour_of_day, day_of_week, created_at) "
            "SELECT journey_id, from_station_code, to_station_code, data_source, "
            "line_code, scheduled_minutes, actual_minutes, delay_minutes, "
            "departure_time, hour_of_day, day_of_week, created_at "
            "FROM segment_transit_times_legacy WHERE id = ANY(:ids)"
        ),
        cutoff_is_timestamptz=True,
    ),
)


async def _table_exists(db: AsyncSession, table: str) -> bool:
    result = await db.execute(text("SELECT to_regclass(:t)"), {"t": table})
    return result.scalar() is not None


async def _get_backfill_state(
    db: AsyncSession, legacy_table: str
) -> tuple[int | None, bool]:
    """Return (last_copied_id, completed) for a legacy table, creating the
    state row on first sight. last_copied_id is the lowest legacy id copied so
    far (we copy newest-first); None means nothing copied yet."""
    result = await db.execute(
        text(
            f"SELECT last_copied_id, completed FROM {BACKFILL_STATE_TABLE} "
            "WHERE legacy_table = :t"
        ),
        {"t": legacy_table},
    )
    row = result.first()
    if row is None:
        await db.execute(
            text(
                f"INSERT INTO {BACKFILL_STATE_TABLE} (legacy_table) VALUES (:t) "
                "ON CONFLICT (legacy_table) DO NOTHING"
            ),
            {"t": legacy_table},
        )
        return None, False
    return row[0], row[1]


async def backfill_one_batch(
    db: AsyncSession,
    cfg: LegacyBackfill,
    cutoff_date: date,
    batch_size: int = BACKFILL_BATCH_SIZE,
) -> tuple[int, bool]:
    """Copy one batch of rows from a `*_legacy` table into its partitioned
    replacement. Returns (rows_copied, completed_now). Idempotent across
    restarts via the persisted cursor. No-op (0, True) once already complete."""
    last_copied_id, completed = await _get_backfill_state(db, cfg.legacy_table)
    if completed:
        return 0, True

    cutoff: date | datetime = cutoff_date
    if cfg.cutoff_is_timestamptz:
        cutoff = datetime.combine(cutoff_date, time.min, tzinfo=timezone.utc)

    params: dict[str, object] = {"cutoff": cutoff, "batch": batch_size}
    cursor_sql = ""
    if last_copied_id is not None:
        cursor_sql = cfg.cursor_clause
        params["cursor"] = last_copied_id

    id_rows = await db.execute(
        text(cfg.select_ids_sql.format(cursor=cursor_sql)), params
    )
    ids = [r[0] for r in id_rows]

    if not ids:
        await db.execute(
            text(
                f"UPDATE {BACKFILL_STATE_TABLE} SET completed = true, "
                "updated_at = now() WHERE legacy_table = :t"
            ),
            {"t": cfg.legacy_table},
        )
        logger.info("legacy_backfill_completed", legacy_table=cfg.legacy_table)
        return 0, True

    await db.execute(text(cfg.insert_sql), {"ids": ids})
    await db.execute(
        text(
            f"UPDATE {BACKFILL_STATE_TABLE} SET last_copied_id = :min_id, "
            "rows_copied = rows_copied + :n, updated_at = now() "
            "WHERE legacy_table = :t"
        ),
        {"min_id": min(ids), "n": len(ids), "t": cfg.legacy_table},
    )
    logger.info(
        "legacy_backfill_batch",
        legacy_table=cfg.legacy_table,
        rows_copied=len(ids),
        min_id=min(ids),
    )
    return len(ids), False


async def drop_backfilled_legacy_table(db: AsyncSession, cfg: LegacyBackfill) -> bool:
    """Drop a `*_legacy` table once its backfill has completed, reclaiming its
    space in one shot. Returns True if a drop happened. Safe/idempotent: only
    drops when state says completed and the table still exists."""
    _, completed = await _get_backfill_state(db, cfg.legacy_table)
    if not completed or not await _table_exists(db, cfg.legacy_table):
        return False
    await db.execute(text(f"DROP TABLE IF EXISTS {cfg.legacy_table}"))
    logger.info("legacy_table_dropped", legacy_table=cfg.legacy_table)
    return True


async def run_legacy_backfill_batches(
    db: AsyncSession,
    cutoff_date: date,
    max_batches: int = BACKFILL_MAX_BATCHES_PER_RUN,
    batch_size: int = BACKFILL_BATCH_SIZE,
) -> dict[str, dict[str, object]]:
    """Advance the legacy backfill by up to `max_batches` per legacy table, and
    drop any legacy table whose backfill has just completed. No-op for tables
    already dropped. Returns a per-legacy-table summary. The caller owns the
    transaction (commit after this returns)."""
    summary: dict[str, dict[str, object]] = {}
    for cfg in LEGACY_BACKFILLS:
        if not await _table_exists(db, cfg.legacy_table):
            continue

        copied_total = 0
        completed = False
        for _ in range(max_batches):
            copied, completed = await backfill_one_batch(
                db, cfg, cutoff_date, batch_size
            )
            copied_total += copied
            if completed or copied == 0:
                break

        if completed:
            await drop_backfilled_legacy_table(db, cfg)

        summary[cfg.legacy_table] = {
            "rows_copied": copied_total,
            "completed": completed,
        }

    return summary
