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

from trackrat.db.partitioning import drop_old_partitions, ensure_future_partitions
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
