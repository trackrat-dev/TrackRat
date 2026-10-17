"""
Integration tests for migration c96a9e34aa8b (issue #1839), run against real
Postgres: rows stored with NJT's raw line codes are rewritten to TrackRat's
canonical codes in train_journeys and the two tables that copy its line_code.

Until #1839 journey collection stored getTrainStopList's LINECODE verbatim
("ML", "BC", "GS", "MC") and discovery stored the real-time "No Jersey Coast"
as "No". No route_topology line_codes set contains those, so the rows were
invisible to the track predictor, delay forecaster, line-mode route alerts
and route-history baselines, all of which filter on exact line_code.
"""

import importlib
from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from trackrat.models.database import SegmentTransitTime, StationDwellTime, TrainJourney

migration = importlib.import_module(
    "trackrat.db.migrations.versions."
    "20261004_0008-c96a9e34aa8b_canonicalize_raw_njt_line_codes"
)

DEPARTURE = datetime(2026, 10, 1, 16, 39, tzinfo=UTC)


def _run_upgrade(session: Session) -> None:
    context = MigrationContext.configure(session.connection())
    with Operations.context(context):
        migration.upgrade()


async def _add_journey(
    db: AsyncSession,
    *,
    train_id: str,
    line_code: str,
    line_name: str,
    data_source: str = "NJT",
) -> TrainJourney:
    """A journey with one segment and one dwell row carrying its line_code."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=DEPARTURE.date(),
        line_code=line_code,
        line_name=line_name,
        destination="Somewhere",
        origin_station_code="HB",
        terminal_station_code="SF",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=DEPARTURE,
        is_cancelled=False,
        has_complete_journey=True,
        stops_count=2,
    )
    db.add(journey)
    await db.flush()
    db.add(
        SegmentTransitTime(
            journey_id=journey.id,
            from_station_code="HB",
            to_station_code="SE",
            data_source=data_source,
            line_code=line_code,
            scheduled_minutes=10,
            actual_minutes=11,
            delay_minutes=1,
            departure_time=DEPARTURE,
            hour_of_day=12,
            day_of_week=3,
        )
    )
    db.add(
        StationDwellTime(
            journey_id=journey.id,
            station_code="SE",
            data_source=data_source,
            line_code=line_code,
            scheduled_minutes=1,
            actual_minutes=1,
            excess_dwell_minutes=0,
            departure_time=DEPARTURE,
            hour_of_day=12,
            day_of_week=3,
        )
    )
    await db.flush()
    return journey


async def _codes(db: AsyncSession, journey_id: int) -> tuple[str, str, str]:
    """(train_journeys, segment_transit_times, station_dwell_times) codes."""
    db.expire_all()
    journey_code = await db.scalar(
        select(TrainJourney.line_code).where(TrainJourney.id == journey_id)
    )
    segment_code = await db.scalar(
        select(SegmentTransitTime.line_code).where(
            SegmentTransitTime.journey_id == journey_id
        )
    )
    dwell_code = await db.scalar(
        select(StationDwellTime.line_code).where(
            StationDwellTime.journey_id == journey_id
        )
    )
    return journey_code, segment_code, dwell_code


class TestCanonicalizeRawNjtLineCodes:
    @pytest.mark.parametrize(
        ("raw", "line_name", "expected"),
        [
            ("ML", "Main Line", "MA"),
            ("BC", "Bergen County Line", "BE"),
            ("GS", "Gladstone Branch", "GL"),
            ("MC", "Montclair-Boonton", "MO"),
            ("No", "North Jersey Coast Line", "NC"),
            ("No", "No Jersey Coast", "NC"),
        ],
    )
    async def test_raw_code_rewritten_in_every_table(
        self, db_session: AsyncSession, raw: str, line_name: str, expected: str
    ) -> None:
        journey = await _add_journey(
            db_session, train_id="1785", line_code=raw, line_name=line_name
        )

        await db_session.run_sync(_run_upgrade)

        codes = await _codes(db_session, journey.id)
        print(f"{raw!r} ({line_name}) -> {codes}")
        assert codes == (expected, expected, expected)

    async def test_derived_no_rows_of_a_healed_coast_journey(
        self, db_session: AsyncSession
    ) -> None:
        """Journey collection healed the journey to NC (LINECODE "NC") after
        its segments were analyzed under discovery's "No": the derived rows
        are still fixed, found through the journey's line_name."""
        journey = await _add_journey(
            db_session,
            train_id="7269",
            line_code="No",
            line_name="North Jersey Coast Line",
        )
        journey.line_code = "NC"
        await db_session.flush()

        await db_session.run_sync(_run_upgrade)

        codes = await _codes(db_session, journey.id)
        print(f"healed coast journey -> {codes}")
        assert codes == ("NC", "NC", "NC")

    async def test_ambiguous_and_foreign_codes_untouched(
        self, db_session: AsyncSession
    ) -> None:
        """'No' from the old "Northeast Corridor" truncation is not the Coast
        Line; canonical NJT codes need no change; and the subway's 42nd St
        Shuttle legitimately uses "GS"."""
        cases = [
            ("3227", "No", "Northeast Corridor", "NJT"),
            ("9147", "MA", "Main Line", "NJT"),
            ("S42", "GS", "42 St Shuttle", "SUBWAY"),
        ]
        journey_ids = [
            (
                await _add_journey(
                    db_session,
                    train_id=train_id,
                    line_code=code,
                    line_name=name,
                    data_source=source,
                )
            ).id
            for train_id, code, name, source in cases
        ]

        await db_session.run_sync(_run_upgrade)

        for journey_id, (_, code, name, source) in zip(journey_ids, cases, strict=True):
            codes = await _codes(db_session, journey_id)
            print(f"{source} {name!r} -> {codes}")
            assert codes == (code, code, code)

    async def test_upgrade_is_idempotent(self, db_session: AsyncSession) -> None:
        journey = await _add_journey(
            db_session, train_id="1785", line_code="BC", line_name="Bergen"
        )

        await db_session.run_sync(_run_upgrade)
        await db_session.run_sync(_run_upgrade)

        assert await _codes(db_session, journey.id) == ("BE", "BE", "BE")
