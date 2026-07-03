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
from datetime import date

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
