"""
Integration tests for migration e3921513ad63 (issue #1883), run against real
Postgres: NJT rows whose line code came from truncating an unrecognized
real-time LINE name ("Septa" -> "Se", "BetMGM Meadowlands" -> "Be",
"DoorDash Meadowlands Line" -> "Do") are rewritten to NJT's own LINECODE
("SP", "SL") in train_journeys and the two tables that copy its line_code.

"Be" is also Bergen County's legacy alias, so the Meadowlands rewrite must be
confined to rows whose journey line_name names the Meadowlands.
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
    "20261011_1747-e3921513ad63_backfill_njt_septa_and_meadowlands_line_"
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


class TestBackfillSeptaAndMeadowlandsLineCodes:
    @pytest.mark.parametrize(
        ("raw", "line_name", "expected"),
        [
            ("Be", "BetMGM Meadowlands", "SL"),
            ("Do", "DoorDash Meadowlands Line", "SL"),
            # Discovery stores the real-time LINE_NAME, blank for SEPTA trains
            # (staging serves S7204 on 2026-10-09 as {code: "Se", name: "Se"}).
            ("Se", "", "SP"),
            ("Se", "Septa", "SP"),
        ],
    )
    async def test_truncated_code_rewritten_in_every_table(
        self, db_session: AsyncSession, raw: str, line_name: str, expected: str
    ) -> None:
        journey = await _add_journey(
            db_session, train_id="1904", line_code=raw, line_name=line_name
        )

        await db_session.run_sync(_run_upgrade)

        codes = await _codes(db_session, journey.id)
        print(f"{raw!r} ({line_name!r}) -> {codes}")
        assert codes == (expected, expected, expected)

    async def test_derived_rows_of_a_healed_meadowlands_journey(
        self, db_session: AsyncSession
    ) -> None:
        """Journey collection healed the journey to SL (LINECODE "SL") after
        its segments were analyzed under discovery's "Be": the derived rows
        are still fixed, found through the journey's line_name."""
        journey = await _add_journey(
            db_session,
            train_id="1910",
            line_code="Be",
            line_name="BetMGM Meadowlands",
        )
        journey.line_code = "SL"
        await db_session.flush()

        await db_session.run_sync(_run_upgrade)

        codes = await _codes(db_session, journey.id)
        print(f"healed Meadowlands journey -> {codes}")
        assert codes == ("SL", "SL", "SL")

    async def test_bergen_and_foreign_codes_untouched(
        self, db_session: AsyncSession
    ) -> None:
        """Pre-2026-03 Bergen County rows legitimately carry "Be"; a "Do" row
        not named for the Meadowlands is not provably one; and only NJT rows
        are rewritten."""
        cases = [
            ("1157", "Be", "Bergen County Line", "NJT"),
            ("1159", "Do", "Unknown", "NJT"),
            ("X1", "Se", "Septa", "SEPTA_RR"),
            ("X2", "Be", "BetMGM Meadowlands", "AMTRAK"),
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
            print(f"{source} {code!r} ({name!r}) -> {codes}")
            assert codes == (code, code, code)

    async def test_upgrade_is_idempotent(self, db_session: AsyncSession) -> None:
        journey = await _add_journey(
            db_session, train_id="1904", line_code="Be", line_name="BetMGM Meadowlands"
        )

        await db_session.run_sync(_run_upgrade)
        await db_session.run_sync(_run_upgrade)

        assert await _codes(db_session, journey.id) == ("SL", "SL", "SL")
