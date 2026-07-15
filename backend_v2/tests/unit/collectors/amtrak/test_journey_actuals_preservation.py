"""
Unit tests for Amtrak actuals preservation and the durable origin-departure
signal (issues #1501 / #1502).

The Amtraker feed trims already-passed stations from a running train's stop
list. Two interlocking defects:

- #1502: both stop-sync sites deleted any DB stop absent from the feed, so
  passed stops — carrying actual_arrival/actual_departure/track — were
  irreversibly destroyed on every refresh. Origin-keyed queries stopped
  matching mid-run, completed journeys kept only tail stops, and the pattern
  scheduler's required-origin consensus starved.
- #1501: journey.actual_departure had exactly one writer
  (_convert_to_journey), which never re-runs once a row is OBSERVED — so on
  the JIT-only lifecycle the #1490 expiry gate's durable signal was never
  written and the gate degraded to the surviving-departed-stop fallback that
  the deletion was simultaneously eroding.

Fixes under test: the deletion now only removes stops with no recorded
reality (template stops the train doesn't serve never acquire actuals, so
they are still cleaned up); feed stops are renumbered AFTER preserved
trimmed stops so sequences never collide; and collect_journey_details
records journey.actual_departure write-once from the origin stop.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.amtrak import (
    create_amtrak_station_data,
    create_amtrak_train_data,
)
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture
def journey_collector():
    return AmtrakJourneyCollector()


def _iso(dt) -> str:
    return dt.isoformat()


def _observed_journey(actual_departure=None) -> TrainJourney:
    return TrainJourney(
        train_id="A2150",
        journey_date=date.today(),
        line_code="NEC",
        line_name="Northeast Regional",
        destination="Washington",
        origin_station_code="NY",
        terminal_station_code="WS",
        data_source="AMTRAK",
        scheduled_departure=now_et() - timedelta(hours=2),
        actual_departure=actual_departure,
        has_complete_journey=True,
        is_completed=False,
        is_expired=False,
        api_error_count=0,
        update_count=1,
        observation_type="OBSERVED",
    )


def _mock_feed(journey_collector, train_data) -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_all_trains.return_value = {"2150": [train_data]}
    journey_collector.client = mock_client


class TestTrimmedStopPreservation:
    @pytest.mark.asyncio
    async def test_trimmed_departed_stop_survives_refresh(
        self, db_session: AsyncSession, journey_collector
    ):
        """A passed stop with recorded actuals must survive a refresh whose
        feed has trimmed it, keeping its actuals, track, and sequence — and
        the surviving feed stops must be renumbered AFTER it, not from 0.
        """
        origin_sched = now_et().replace(microsecond=0) - timedelta(hours=2)
        origin_actual = origin_sched + timedelta(minutes=3)

        journey = _observed_journey()
        db_session.add(journey)
        await db_session.flush()

        db_session.add_all(
            [
                JourneyStop(
                    journey=journey,
                    station_code="NY",
                    station_name="New York Penn Station",
                    stop_sequence=0,
                    scheduled_departure=origin_sched,
                    actual_departure=origin_actual,
                    has_departed_station=True,
                    track="9",
                ),
                JourneyStop(
                    journey=journey,
                    station_code="NP",
                    station_name="Newark Penn Station",
                    stop_sequence=1,
                    scheduled_arrival=origin_sched + timedelta(minutes=15),
                    has_departed_station=False,
                ),
                JourneyStop(
                    journey=journey,
                    station_code="WS",
                    station_name="Washington Union",
                    stop_sequence=2,
                    scheduled_arrival=origin_sched + timedelta(hours=3),
                    has_departed_station=False,
                ),
            ]
        )
        await db_session.flush()

        # Mid-run feed: NYP has been trimmed (already passed).
        train_data = create_amtrak_train_data(
            train_id="2150-13",
            train_num="2150",
            route="Northeast Regional",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NWK",
                    name="Newark Penn",
                    sch_arr=_iso(origin_sched + timedelta(minutes=15)),
                    sch_dep=_iso(origin_sched + timedelta(minutes=17)),
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="WAS",
                    name="Washington Union",
                    sch_arr=_iso(origin_sched + timedelta(hours=3)),
                    status="Enroute",
                ),
            ],
        )
        _mock_feed(journey_collector, train_data)

        await journey_collector.collect_journey_details(db_session, journey)
        await db_session.refresh(journey)

        stops = (
            (
                await db_session.execute(
                    select(JourneyStop)
                    .where(JourneyStop.journey_id == journey.id)
                    .order_by(JourneyStop.stop_sequence)
                )
            )
            .scalars()
            .all()
        )
        codes = [s.station_code for s in stops]
        assert codes == ["NY", "NP", "WS"], (
            "The trimmed-but-departed origin must survive the refresh; "
            f"got {codes} (issue #1502)"
        )

        origin_stop = stops[0]
        assert origin_stop.actual_departure == origin_actual, (
            "Recorded origin actual_departure must not be destroyed by the "
            "stale-stop deletion"
        )
        assert origin_stop.has_departed_station is True
        assert origin_stop.track == "9"

        assert [s.stop_sequence for s in stops] == [0, 1, 2], (
            "Feed stops must be renumbered AFTER the preserved origin — "
            "renumbering from 0 would collide with the preserved sequence"
        )
        assert (
            journey.stops_count == 3
        ), "stops_count must include preserved trimmed stops"
        assert journey.terminal_station_code == "WS"

    @pytest.mark.asyncio
    async def test_template_stops_without_actuals_still_deleted(
        self, db_session: AsyncSession, journey_collector
    ):
        """The deletion's original purpose is preserved: stops with no
        recorded reality (pattern-scheduler template stops for stations the
        train doesn't serve) are still removed.
        """
        origin_sched = now_et().replace(microsecond=0) - timedelta(hours=2)

        journey = _observed_journey()
        db_session.add(journey)
        await db_session.flush()

        db_session.add_all(
            [
                JourneyStop(
                    journey=journey,
                    station_code="NY",
                    station_name="New York Penn Station",
                    stop_sequence=0,
                    scheduled_departure=origin_sched,
                    has_departed_station=False,
                ),
                # Stale template stop — never served, no actuals.
                JourneyStop(
                    journey=journey,
                    station_code="MP",
                    station_name="Metropark",
                    stop_sequence=1,
                    scheduled_arrival=origin_sched + timedelta(minutes=25),
                    has_departed_station=False,
                ),
                JourneyStop(
                    journey=journey,
                    station_code="WS",
                    station_name="Washington Union",
                    stop_sequence=2,
                    scheduled_arrival=origin_sched + timedelta(hours=3),
                    has_departed_station=False,
                ),
            ]
        )
        await db_session.flush()

        train_data = create_amtrak_train_data(
            train_id="2150-13",
            train_num="2150",
            route="Northeast Regional",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn",
                    sch_dep=_iso(origin_sched),
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="WAS",
                    name="Washington Union",
                    sch_arr=_iso(origin_sched + timedelta(hours=3)),
                    status="Enroute",
                ),
            ],
        )
        _mock_feed(journey_collector, train_data)

        await journey_collector.collect_journey_details(db_session, journey)

        codes = [
            s.station_code
            for s in (
                await db_session.execute(
                    select(JourneyStop)
                    .where(JourneyStop.journey_id == journey.id)
                    .order_by(JourneyStop.stop_sequence)
                )
            )
            .scalars()
            .all()
        ]
        assert "MP" not in codes, (
            "A template stop with no actuals must still be cleaned up; " f"got {codes}"
        )
        assert codes == ["NY", "WS"]


class TestDurableActualDeparture:
    @pytest.mark.asyncio
    async def test_actual_departure_recorded_from_origin_stop(
        self, db_session: AsyncSession, journey_collector
    ):
        """collect_journey_details must record journey.actual_departure when
        the origin stop reports departure — previously nothing wrote it after
        conversion, hollowing out the #1490 expiry gate (issue #1501).
        """
        origin_sched = now_et().replace(microsecond=0) - timedelta(hours=1)
        origin_actual = origin_sched + timedelta(minutes=4)

        journey = _observed_journey(actual_departure=None)
        db_session.add(journey)
        await db_session.flush()

        train_data = create_amtrak_train_data(
            train_id="2150-13",
            train_num="2150",
            route="Northeast Regional",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn",
                    sch_dep=_iso(origin_sched),
                    actual_dep=_iso(origin_actual),
                    status="Departed",
                ),
                create_amtrak_station_data(
                    code="WAS",
                    name="Washington Union",
                    sch_arr=_iso(origin_sched + timedelta(hours=3)),
                    status="Enroute",
                ),
            ],
        )
        _mock_feed(journey_collector, train_data)

        await journey_collector.collect_journey_details(db_session, journey)
        await db_session.refresh(journey)

        assert journey.actual_departure == origin_actual, (
            "journey.actual_departure must be recorded from the origin stop "
            "on the refresh path (issue #1501)"
        )

        # The durable signal must now satisfy the #1490 expiry gate even
        # after the feed later trims the origin stop.
        assert await journey_collector._has_departed_origin(db_session, journey) is True

    @pytest.mark.asyncio
    async def test_actual_departure_is_write_once(
        self, db_session: AsyncSession, journey_collector
    ):
        """An already-recorded journey.actual_departure is never overwritten
        by later refreshes.
        """
        origin_sched = now_et().replace(microsecond=0) - timedelta(hours=1)
        recorded = origin_sched + timedelta(minutes=4)

        journey = _observed_journey(actual_departure=recorded)
        db_session.add(journey)
        await db_session.flush()

        train_data = create_amtrak_train_data(
            train_id="2150-13",
            train_num="2150",
            route="Northeast Regional",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn",
                    sch_dep=_iso(origin_sched),
                    # Feed now serves a different (drifted) value.
                    actual_dep=_iso(origin_sched + timedelta(minutes=9)),
                    status="Departed",
                ),
                create_amtrak_station_data(
                    code="WAS",
                    name="Washington Union",
                    sch_arr=_iso(origin_sched + timedelta(hours=3)),
                    status="Enroute",
                ),
            ],
        )
        _mock_feed(journey_collector, train_data)

        await journey_collector.collect_journey_details(db_session, journey)
        await db_session.refresh(journey)

        assert (
            journey.actual_departure == recorded
        ), "journey.actual_departure is a write-once durable signal"
