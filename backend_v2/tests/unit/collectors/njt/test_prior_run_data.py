"""
Tests for issue #1996: today's NJT journey overwritten with the previous day's run.

getTrainStopList is keyed by train number alone. Shortly after midnight NJT
still returns *yesterday's* completed run for a train number, and the nightly
schedule pass fetches today's run for tomorrow's rows. Applied to the newer
row, that run's schedule, actuals and DEPARTED flags marked 14 trains as
completed before they ran (2026-11-22). `_is_same_journey` skipped its
departure-time check for rows without `has_complete_journey`, so nothing caught it.

These tests pin `is_prior_run_response` and both writers that apply a stop
list: `JourneyCollector.collect_journey_details` and
`NJTScheduleCollector._update_journey_with_stops`.

Both collectors get a real `NJTransitClient`. Stop lists are supplied through
`prefetched_train_data` (the batch collector's own path) or passed straight to
`_update_journey_with_stops`, so no test reaches the NJT API.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.njt_api_responses import (
    NJT_TIME_FORMAT,
    StopBuilder,
    create_stop_list_response,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import (
    STALE_PRIOR_RUN_THRESHOLD_SECONDS,
    JourneyCollector,
    JourneyMatchResult,
    is_prior_run_response,
)
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


def _today_at(hour: int, minute: int = 0):
    return now_et().replace(hour=hour, minute=minute, second=0, microsecond=0)


def _stop_list(train_id: str, origin_departure, *, departed: bool = False):
    """A two-stop Pascack Valley run (SV → HB) starting at ``origin_departure``."""
    builder = StopBuilder()
    hb_arrival = origin_departure + timedelta(minutes=55)
    return create_stop_list_response(
        train_id=train_id,
        line_code="PV",
        destination="Hoboken",
        stops=[
            builder.build_stop(
                "SV",
                "Spring Valley",
                origin_departure.strftime(NJT_TIME_FORMAT),
                departed=departed,
                sched_dep_date=origin_departure.strftime(NJT_TIME_FORMAT),
            ),
            builder.build_stop(
                "HB",
                "Hoboken",
                hb_arrival.strftime(NJT_TIME_FORMAT),
                arr_time=hb_arrival.strftime(NJT_TIME_FORMAT),
                departed=departed,
            ),
        ],
    )


def _discovery_row(train_id: str, scheduled_departure) -> TrainJourney:
    """Today's row as discovery creates it: one stop, not yet complete."""
    return TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        line_code="PV",
        line_name="Pascack Valley",
        destination="Hoboken",
        origin_station_code="SV",
        terminal_station_code="HB",
        data_source="NJT",
        scheduled_departure=scheduled_departure,
        has_complete_journey=False,
        is_completed=False,
        is_expired=False,
        api_error_count=0,
        observation_type="OBSERVED",
    )


class TestIsPriorRunResponse:
    """The pure classifier: only an *earlier* run beyond 6h counts."""

    def test_previous_day_run_is_prior(self):
        stored = _today_at(19, 16)
        response = _stop_list("2124", stored - timedelta(days=1))
        result = is_prior_run_response(stored, response)
        print(f"stored={stored} api={stored - timedelta(days=1)} -> {result}")
        assert result is True

    def test_threshold_boundary(self):
        stored = _today_at(19, 16)
        threshold = timedelta(seconds=STALE_PRIOR_RUN_THRESHOLD_SECONDS)
        at_threshold = _stop_list("2124", stored - threshold)
        past_threshold = _stop_list("2124", stored - threshold - timedelta(minutes=1))
        print(f"threshold={threshold}")
        assert (
            is_prior_run_response(stored, at_threshold) is False
        ), "Exactly the threshold is not beyond it"
        assert is_prior_run_response(stored, past_threshold) is True

    def test_intermediate_station_discovery_is_not_prior(self):
        """A row discovered mid-route stores a later time than the origin's."""
        origin = _today_at(19, 20)
        stored_at_intermediate = origin + timedelta(minutes=86)
        assert (
            is_prior_run_response(stored_at_intermediate, _stop_list("3879", origin))
            is False
        )

    def test_later_run_is_not_prior(self):
        """The opposite direction is STALE_PRIOR_RUN's case, not this one."""
        stored = _today_at(14, 23) - timedelta(days=1)
        assert (
            is_prior_run_response(
                stored, _stop_list("5517", stored + timedelta(days=1))
            )
            is False
        )

    def test_missing_inputs_are_not_prior(self):
        stored = _today_at(19, 16)
        empty = create_stop_list_response(train_id="2124", stops=[])
        assert is_prior_run_response(None, _stop_list("2124", stored)) is False
        assert is_prior_run_response(stored, empty) is False

    def test_dep_time_fallback_when_sched_dep_date_absent(self):
        stored = _today_at(19, 16)
        builder = StopBuilder()
        response = create_stop_list_response(
            train_id="2124",
            stops=[
                builder.build_stop(
                    "SV",
                    "Spring Valley",
                    (stored - timedelta(days=1)).strftime(NJT_TIME_FORMAT),
                )
            ],
        )
        assert is_prior_run_response(stored, response) is True


@pytest_asyncio.fixture
async def njt_client():
    client = NJTransitClient()
    yield client
    await client.close()


class TestJourneyCollectorPriorRun:
    @pytest.fixture
    def collector(self, njt_client):
        return JourneyCollector(njt_client)

    @pytest.mark.asyncio
    async def test_incomplete_row_rejects_previous_days_run(
        self, db_session: AsyncSession, collector
    ):
        """The exact #1996 shape: discovery row, has_complete_journey=False."""
        today = _today_at(19, 16)
        journey = _discovery_row("2124", today)
        db_session.add(journey)
        await db_session.flush()

        response = _stop_list("2124", today - timedelta(days=1), departed=True)
        response.LINECODE = "BC"

        result = await collector._is_same_journey(db_session, journey, response)
        print(f"result={result} line_code={journey.line_code}")

        assert result is JourneyMatchResult.PRIOR_RUN_DATA
        assert (
            journey.line_code == "PV"
        ), "Nothing from the prior run may be adopted, not even the line code"

    @pytest.mark.asyncio
    async def test_complete_row_rejects_previous_days_run_without_strike(
        self, db_session: AsyncSession, collector
    ):
        """A complete row used to take a DEPARTURE_TIME_MISMATCH strike here."""
        today = _today_at(19, 16)
        journey = _discovery_row("2126", today)
        journey.has_complete_journey = True
        db_session.add(journey)
        await db_session.flush()

        result = await collector._is_same_journey(
            db_session, journey, _stop_list("2126", today - timedelta(days=1))
        )
        assert result is JourneyMatchResult.PRIOR_RUN_DATA

    @pytest.mark.asyncio
    async def test_collect_journey_details_leaves_row_untouched(
        self, db_session: AsyncSession, collector
    ):
        today = _today_at(19, 16)
        journey = _discovery_row("2124", today)
        db_session.add(journey)
        await db_session.flush()
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="SV",
                station_name="Spring Valley",
                stop_sequence=0,
                scheduled_departure=today,
                has_departed_station=False,
            )
        )
        await db_session.flush()

        await collector.collect_journey_details(
            db_session,
            journey,
            prefetched_train_data=_stop_list(
                "2124", today - timedelta(days=1), departed=True
            ),
        )
        await db_session.refresh(journey)
        stops = (
            await db_session.scalars(
                select(JourneyStop).where(JourneyStop.journey_id == journey.id)
            )
        ).all()
        print(
            f"completed={journey.is_completed} expired={journey.is_expired} "
            f"sched={journey.scheduled_departure} strikes={journey.api_error_count} "
            f"stops={[(s.station_code, s.has_departed_station, s.actual_departure) for s in stops]}"
        )

        assert journey.is_completed is False
        assert journey.is_expired is False
        assert journey.has_complete_journey is False
        assert journey.scheduled_departure == today
        assert journey.api_error_count == 0, "Prior-run data is not a strike"
        assert journey.last_updated_at is not None, "The refresh must be stamped"
        assert [s.station_code for s in stops] == ["SV"]
        assert stops[0].has_departed_station is False
        assert stops[0].actual_departure is None

    @pytest.mark.asyncio
    async def test_collect_journey_details_still_applies_todays_run(
        self, db_session: AsyncSession, collector
    ):
        """Control: the same row accepts its own day's run.

        skip_enhancement keeps the departure-board lookup (a live NJT call when
        the 19:16 departure is within 15 minutes of the test run) out of a test
        about the prior-run guard.
        """
        today = _today_at(19, 16)
        journey = _discovery_row("2125", today)
        db_session.add(journey)
        await db_session.flush()

        await collector.collect_journey_details(
            db_session,
            journey,
            skip_enhancement=True,
            prefetched_train_data=_stop_list("2125", today),
        )
        await db_session.refresh(journey)
        print(f"has_complete_journey={journey.has_complete_journey}")

        assert journey.has_complete_journey is True
        assert journey.scheduled_departure == today


class TestScheduleCollectorPriorRun:
    @pytest.fixture
    def collector(self, njt_client):
        return NJTScheduleCollector(njt_client)

    async def _scheduled_row(self, session: AsyncSession, train_id: str, departure):
        journey = _discovery_row(train_id, departure)
        journey.observation_type = "SCHEDULED"
        session.add(journey)
        await session.flush()
        session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="SV",
                station_name="Spring Valley",
                stop_sequence=0,
                scheduled_departure=departure,
            )
        )
        await session.flush()
        return journey

    @pytest.mark.asyncio
    async def test_tomorrows_row_is_not_rebuilt_from_todays_run(
        self, db_session: AsyncSession, collector
    ):
        tomorrow = _today_at(7, 30) + timedelta(days=1)
        journey = await self._scheduled_row(db_session, "1789", tomorrow)

        await collector._update_journey_with_stops(
            db_session, journey, _stop_list("1789", tomorrow - timedelta(days=1))
        )
        await db_session.refresh(journey)
        stops = (
            await db_session.scalars(
                select(JourneyStop).where(JourneyStop.journey_id == journey.id)
            )
        ).all()
        print(
            f"sched={journey.scheduled_departure} complete={journey.has_complete_journey} "
            f"stops={[s.station_code for s in stops]}"
        )

        assert journey.scheduled_departure == tomorrow
        assert journey.has_complete_journey is False
        assert [s.station_code for s in stops] == ["SV"], "Placeholder must survive"

    @pytest.mark.asyncio
    async def test_same_day_run_is_applied(self, db_session: AsyncSession, collector):
        today = _today_at(7, 30)
        journey = await self._scheduled_row(db_session, "7276", today)

        await collector._update_journey_with_stops(
            db_session, journey, _stop_list("7276", today)
        )
        await db_session.refresh(journey)
        stops = (
            await db_session.scalars(
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence)
            )
        ).all()

        assert journey.has_complete_journey is True
        assert [s.station_code for s in stops] == ["SV", "HB"]
