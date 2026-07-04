"""
Integration tests for journey_stops / segment_transit_times partitioning
(issue #1343).

Exercises the real Postgres partitioned schema created by
`Base.metadata.create_all()` (see conftest.py's `db_engine` fixture): insert
routing (both via the ORM `journey` relationship and via a bare journey_id),
cascade delete across a partitioned child table, and reclaiming space by
dropping an aged-out partition.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.db.partitioning import (
    drop_old_partitions,
    ensure_future_partitions,
    run_legacy_backfill_batches,
)
from trackrat.models.database import JourneyStop, SegmentTransitTime, TrainJourney


def _make_journey(journey_date: date, train_id: str = "1234") -> TrainJourney:
    return TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        line_code="NEC",
        destination="WAS",
        origin_station_code="NY",
        terminal_station_code="WAS",
        data_source="AMTRAK",
        observation_type="OBSERVED",
        scheduled_departure=datetime(
            journey_date.year,
            journey_date.month,
            journey_date.day,
            12,
            0,
            tzinfo=UTC,
        ),
    )


@pytest.mark.asyncio
class TestJourneyStopsPartitioning:
    async def test_relationship_construction_populates_journey_date(
        self, db_session: AsyncSession
    ):
        """JourneyStop(journey=..., ...) should auto-populate journey_date
        via the `@validates("journey")` hook, with no explicit journey_date."""
        journey = _make_journey(date.today())
        db_session.add(journey)
        await db_session.flush()

        stop = JourneyStop(journey=journey, station_code="NY", station_name="New York")
        db_session.add(stop)
        await db_session.commit()

        assert stop.journey_date == journey.journey_date

    async def test_bare_journey_id_requires_explicit_journey_date(
        self, db_session: AsyncSession
    ):
        """Collectors that only have journey_id (no TrainJourney object) must
        pass journey_date explicitly — this is how all the GTFS-RT collectors
        construct stops."""
        journey = _make_journey(date.today())
        db_session.add(journey)
        await db_session.flush()

        stop = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="WAS",
            station_name="Washington",
        )
        db_session.add(stop)
        await db_session.commit()

        assert stop.journey_date == journey.journey_date

    async def test_stops_land_in_the_correct_month_partition(
        self, db_session: AsyncSession
    ):
        journey = _make_journey(date.today())
        db_session.add(journey)
        await db_session.flush()

        stop = JourneyStop(journey=journey, station_code="NY", station_name="New York")
        db_session.add(stop)
        await db_session.commit()

        expected_partition = (
            f"journey_stops_y{journey.journey_date.year:04d}"
            f"_m{journey.journey_date.month:02d}"
        )
        result = await db_session.execute(
            text("SELECT tableoid::regclass::text FROM journey_stops WHERE id = :id"),
            {"id": stop.id},
        )
        assert result.scalar_one() == expected_partition

    async def test_cascade_delete_removes_partitioned_child_rows(
        self, db_session: AsyncSession
    ):
        journey = _make_journey(date.today())
        db_session.add(journey)
        await db_session.flush()
        journey_id = journey.id

        db_session.add(
            JourneyStop(journey=journey, station_code="NY", station_name="New York")
        )
        db_session.add(
            SegmentTransitTime(
                journey_id=journey.id,
                from_station_code="NY",
                to_station_code="WAS",
                data_source="AMTRAK",
                scheduled_minutes=180,
                actual_minutes=185,
                delay_minutes=5,
                departure_time=journey.scheduled_departure,
                hour_of_day=12,
                day_of_week=journey.scheduled_departure.weekday(),
            )
        )
        await db_session.commit()

        await db_session.execute(
            text("DELETE FROM train_journeys WHERE id = :id"), {"id": journey_id}
        )
        await db_session.commit()

        stop_count = await db_session.scalar(
            select(func.count()).select_from(JourneyStop)
        )
        segment_count = await db_session.scalar(
            select(func.count()).select_from(SegmentTransitTime)
        )
        assert stop_count == 0
        assert segment_count == 0

    async def test_ensure_future_partitions_is_idempotent(
        self, db_session: AsyncSession
    ):
        # create_all()'s after_create DDL event already bootstrapped the
        # rolling window; calling it again must not error (CREATE TABLE IF
        # NOT EXISTS) and must not duplicate partitions.
        await ensure_future_partitions(db_session)
        await ensure_future_partitions(db_session)
        await db_session.commit()

        result = await db_session.execute(
            text(
                "SELECT count(*) FROM pg_inherits "
                "JOIN pg_class parent ON pg_inherits.inhparent = parent.oid "
                "WHERE parent.relname = 'journey_stops'"
            )
        )
        # 1 default + (1 back + current + 2 forward) = 5, regardless of how
        # many times ensure_future_partitions runs.
        assert result.scalar_one() == 5

    async def test_drop_old_partitions_reclaims_aged_out_data_only(
        self, db_session: AsyncSession
    ):
        """Dropping an old partition removes its rows; a journey in a
        still-live partition is untouched."""
        old_date = date.today() - timedelta(days=400)
        old_journey = _make_journey(old_date, train_id="OLD1")
        db_session.add(old_journey)
        await db_session.flush()

        # The old month is well outside the default rolling window bootstrapped
        # by create_all() — create it explicitly so the insert has somewhere
        # to land.
        await ensure_future_partitions(db_session, reference_date=old_date)
        db_session.add(
            JourneyStop(journey=old_journey, station_code="NY", station_name="New York")
        )

        recent_journey = _make_journey(date.today(), train_id="NEW1")
        db_session.add(recent_journey)
        await db_session.flush()
        db_session.add(
            JourneyStop(
                journey=recent_journey, station_code="NY", station_name="New York"
            )
        )
        await db_session.commit()

        stop_count_before = await db_session.scalar(
            select(func.count()).select_from(JourneyStop)
        )
        assert stop_count_before == 2

        cutoff = date.today() - timedelta(days=60)
        dropped = await drop_old_partitions(db_session, cutoff)
        await db_session.commit()

        assert "journey_stops" in dropped
        expected_partition = f"journey_stops_y{old_date.year:04d}_m{old_date.month:02d}"
        assert expected_partition in dropped["journey_stops"]

        stop_count_after = await db_session.scalar(
            select(func.count()).select_from(JourneyStop)
        )
        assert stop_count_after == 1

        remaining = await db_session.scalar(select(JourneyStop.journey_id).limit(1))
        assert remaining == recent_journey.id

    async def test_drop_old_partitions_leaves_default_partition_alone(
        self, db_session: AsyncSession
    ):
        cutoff = date.today() + timedelta(days=365 * 100)  # absurdly far future
        dropped = await drop_old_partitions(db_session, cutoff)
        await db_session.commit()

        # Even with a cutoff far beyond every dated partition, the DEFAULT
        # partition (no naming-convention match) is never a drop candidate.
        assert "journey_stops_default" not in dropped.get("journey_stops", [])
        result = await db_session.execute(
            text(
                "SELECT count(*) FROM pg_inherits "
                "JOIN pg_class parent ON pg_inherits.inhparent = parent.oid "
                "JOIN pg_class child ON pg_inherits.inhrelid = child.oid "
                "WHERE parent.relname = 'journey_stops' "
                "AND child.relname = 'journey_stops_default'"
            )
        )
        assert result.scalar_one() == 1


# Pre-partition schema of the two tables, as migration 03db10760b28 leaves them
# renamed to *_legacy. create_all() (this harness) only builds the new
# partitioned tables, so the backfill tests recreate the legacy shape here.
_CREATE_JOURNEY_STOPS_LEGACY = """
    CREATE TABLE journey_stops_legacy (
        id SERIAL PRIMARY KEY,
        journey_id INTEGER NOT NULL REFERENCES train_journeys(id) ON DELETE CASCADE,
        station_code VARCHAR(10) NOT NULL,
        station_name VARCHAR(100) NOT NULL,
        stop_sequence INTEGER,
        scheduled_arrival TIMESTAMPTZ,
        scheduled_departure TIMESTAMPTZ,
        updated_arrival TIMESTAMPTZ,
        updated_departure TIMESTAMPTZ,
        actual_arrival TIMESTAMPTZ,
        actual_departure TIMESTAMPTZ,
        raw_amtrak_status VARCHAR(50),
        raw_njt_departed_flag VARCHAR(10),
        has_departed_station BOOLEAN NOT NULL DEFAULT false,
        departure_source VARCHAR(30),
        arrival_source VARCHAR(30),
        track VARCHAR(5),
        track_assigned_at TIMESTAMPTZ,
        pickup_only BOOLEAN NOT NULL DEFAULT false,
        dropoff_only BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
"""

_CREATE_SEGMENTS_LEGACY = """
    CREATE TABLE segment_transit_times_legacy (
        id SERIAL PRIMARY KEY,
        journey_id INTEGER NOT NULL REFERENCES train_journeys(id) ON DELETE CASCADE,
        from_station_code VARCHAR(10) NOT NULL,
        to_station_code VARCHAR(10) NOT NULL,
        data_source VARCHAR(10) NOT NULL,
        line_code VARCHAR(15),
        scheduled_minutes INTEGER NOT NULL,
        actual_minutes INTEGER NOT NULL,
        delay_minutes INTEGER NOT NULL,
        departure_time TIMESTAMPTZ NOT NULL,
        hour_of_day INTEGER NOT NULL,
        day_of_week INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""


async def _add_legacy_stop(db: AsyncSession, journey_id: int, station: str) -> None:
    await db.execute(
        text(
            "INSERT INTO journey_stops_legacy "
            "(journey_id, station_code, station_name, has_departed_station) "
            "VALUES (:jid, :code, :name, true)"
        ),
        {"jid": journey_id, "code": station, "name": station},
    )


async def _add_legacy_segment(
    db: AsyncSession, journey_id: int, departure_time: datetime
) -> None:
    await db.execute(
        text(
            "INSERT INTO segment_transit_times_legacy "
            "(journey_id, from_station_code, to_station_code, data_source, "
            "scheduled_minutes, actual_minutes, delay_minutes, departure_time, "
            "hour_of_day, day_of_week) "
            "VALUES (:jid, 'NY', 'WAS', 'AMTRAK', 180, 185, 5, :dt, 12, 3)"
        ),
        {"jid": journey_id, "dt": departure_time},
    )


async def _table_exists(db: AsyncSession, table: str) -> bool:
    result = await db.execute(text("SELECT to_regclass(:t)"), {"t": table})
    return result.scalar() is not None


@pytest.mark.asyncio
class TestLegacyBackfill:
    async def test_backfill_copies_recent_window_derives_journey_date_and_drops(
        self, db_session: AsyncSession
    ):
        """The backfill copies only rows within the retention window into the
        new partitions, derives journey_date from train_journeys for
        journey_stops, and drops each *_legacy table once complete. Rows older
        than the window are discarded with the legacy table (they're past
        retention)."""
        recent = _make_journey(date.today(), train_id="RECENT")
        old = _make_journey(date.today() - timedelta(days=400), train_id="OLD")
        db_session.add_all([recent, old])
        await db_session.flush()

        await db_session.execute(text(_CREATE_JOURNEY_STOPS_LEGACY))
        await db_session.execute(text(_CREATE_SEGMENTS_LEGACY))
        await _add_legacy_stop(db_session, recent.id, "NY")
        await _add_legacy_stop(db_session, old.id, "NY")
        await _add_legacy_segment(db_session, recent.id, recent.scheduled_departure)
        await _add_legacy_segment(
            db_session, old.id, old.scheduled_departure
        )
        await db_session.commit()

        cutoff = date.today() - timedelta(days=60)
        summary = await run_legacy_backfill_batches(db_session, cutoff)
        await db_session.commit()

        assert summary["journey_stops_legacy"]["completed"] is True
        assert summary["segment_transit_times_legacy"]["completed"] is True

        stops = (await db_session.execute(select(JourneyStop))).scalars().all()
        assert len(stops) == 1
        assert stops[0].journey_id == recent.id
        # journey_date is not a column on the legacy table — it must come from
        # the train_journeys join.
        assert stops[0].journey_date == recent.journey_date

        segments = (
            await db_session.execute(select(SegmentTransitTime))
        ).scalars().all()
        assert len(segments) == 1
        assert segments[0].journey_id == recent.id

        assert not await _table_exists(db_session, "journey_stops_legacy")
        assert not await _table_exists(db_session, "segment_transit_times_legacy")

    async def test_backfill_is_resumable_without_duplicating(
        self, db_session: AsyncSession
    ):
        """Copying in tiny batches across multiple invocations (as a restart
        would) copies every windowed row exactly once — the persisted cursor
        prevents re-copying, which matters because segment rows have no unique
        key to dedupe on."""
        journey = _make_journey(date.today(), train_id="RESUME")
        db_session.add(journey)
        await db_session.flush()

        await db_session.execute(text(_CREATE_JOURNEY_STOPS_LEGACY))
        await db_session.execute(text(_CREATE_SEGMENTS_LEGACY))
        for station in ("NY", "NP", "TR", "PJ", "WAS"):
            await _add_legacy_stop(db_session, journey.id, station)
        await db_session.commit()

        cutoff = date.today() - timedelta(days=60)

        # One row per invocation. Segments finish immediately (none present).
        completed = False
        runs = 0
        while not completed and runs < 20:
            summary = await run_legacy_backfill_batches(
                db_session, cutoff, max_batches=1, batch_size=1
            )
            await db_session.commit()
            completed = summary.get("journey_stops_legacy", {}).get(
                "completed", True
            )
            runs += 1

        stop_count = await db_session.scalar(
            select(func.count()).select_from(JourneyStop)
        )
        assert stop_count == 5  # all copied, none duplicated
        assert not await _table_exists(db_session, "journey_stops_legacy")

    async def test_backfill_skips_rows_a_collector_already_wrote(
        self, db_session: AsyncSession
    ):
        """A collector that re-runs after the cutover writes a live row for a
        pre-migration journey into the new table under the same
        (journey_id, station_code, journey_date) key the backfill will later
        try to copy from legacy. Without ON CONFLICT that unique violation
        aborts the whole batch and the cursor never advances — a permanent
        stall that leaves journey_stops_legacy (the ~33 GB) undropped.

        The backfill must instead: keep the collector's newer row, skip the
        stale legacy copy of that key, still copy the non-colliding legacy
        rows, complete, and drop the legacy table.
        """
        journey = _make_journey(date.today(), train_id="COLLIDE")
        db_session.add(journey)
        await db_session.flush()

        # Collector's post-cutover row already in the new partitioned table.
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="NY",
                station_name="COLLECTOR_NY",
            )
        )
        await db_session.flush()

        # Legacy has the same key (collides) plus one that doesn't (WAS).
        await db_session.execute(text(_CREATE_JOURNEY_STOPS_LEGACY))
        await _add_legacy_stop(db_session, journey.id, "NY")
        await _add_legacy_stop(db_session, journey.id, "WAS")
        await db_session.commit()

        cutoff = date.today() - timedelta(days=60)
        summary = await run_legacy_backfill_batches(db_session, cutoff)
        await db_session.commit()

        assert summary["journey_stops_legacy"]["completed"] is True
        assert not await _table_exists(db_session, "journey_stops_legacy")

        stops = {
            s.station_code: s
            for s in (await db_session.execute(select(JourneyStop))).scalars().all()
        }
        assert set(stops) == {"NY", "WAS"}
        # The colliding key kept the collector's row, not the legacy copy.
        assert stops["NY"].station_name == "COLLECTOR_NY"
        # The non-colliding legacy row was still copied.
        assert stops["WAS"].journey_date == journey.journey_date

    async def test_backfill_noop_when_no_legacy_tables(
        self, db_session: AsyncSession
    ):
        """Once the legacy tables are gone (steady state), the task is a cheap
        no-op that copies nothing and reports no tables."""
        summary = await run_legacy_backfill_batches(
            db_session, date.today() - timedelta(days=60)
        )
        assert summary == {}
