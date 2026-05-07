"""
Unit tests for journey mismatch detection resilience.

Tests the fix for false journey expiration when journeys are discovered
at intermediate stations and their metadata becomes stale.

The bug: When departure.py or scheduler.py updates stops but doesn't update
origin_station_code/scheduled_departure, the journey metadata becomes inconsistent.
Later, _is_same_journey() compares the stale scheduled_departure (from discovery
station) against the API's first stop departure (from actual origin), finds a
mismatch > 10 minutes, and falsely expires the journey.

The fix: _is_same_journey() now detects stale origin_station_code by comparing
against the first stop in the stops table. If they don't match, it uses the
stops table's scheduled_departure for comparison instead of the stale journey field.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et

from tests.fixtures.njt_api_responses import (
    NJT_TIME_FORMAT,
    StopBuilder,
    create_stop_list_response,
)


@pytest.fixture
def mock_njt_client():
    """Mock NJ Transit client."""
    client = AsyncMock(spec=NJTransitClient)
    return client


@pytest.fixture
def journey_collector(mock_njt_client):
    """Create journey collector with mocked client."""
    return JourneyCollector(mock_njt_client)


class TestStaleOriginDetection:
    """Test that _is_same_journey() handles stale origin_station_code correctly."""

    @pytest.mark.asyncio
    async def test_uses_stops_table_departure_when_origin_is_stale(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that when origin_station_code doesn't match the first stop in the stops
        table, _is_same_journey() uses the stops table's departure time for comparison.

        Scenario:
        - Journey discovered at Edison (ED) with departure time 8:46 PM
        - Stops collected correctly: first stop is NY Penn at 7:20 PM
        - origin_station_code NOT updated (still ED) - BUG in departure.py/scheduler.py
        - scheduled_departure NOT updated (still 8:46 PM from ED)
        - has_complete_journey = True
        - API returns train with first stop NY Penn at 7:20 PM
        - Without fix: 86 minute difference > 10 min tolerance → FALSE EXPIRATION
        - With fix: Uses stops table departure (7:20 PM), matches → CORRECT MATCH
        """
        # Create timestamps
        base_time = now_et().replace(hour=19, minute=20, second=0, microsecond=0)
        ny_departure = base_time  # 7:20 PM - actual origin departure
        ed_departure = base_time + timedelta(minutes=86)  # 8:46 PM - intermediate stop

        # Create journey with STALE origin (discovered at Edison but never corrected)
        journey = TrainJourney(
            train_id="3879",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="ED",  # STALE - should be NY
            terminal_station_code="ED",  # STALE - should be TR
            data_source="NJT",
            scheduled_departure=ed_departure,  # STALE - should be ny_departure
            has_complete_journey=True,  # Set by departure.py without fixing origin
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # Create CORRECT stops in database (as if departure.py updated them)
        # First stop is NY Penn, not Edison
        stops_data = [
            ("NY", "New York Penn Station", ny_departure, 0),
            ("NP", "Newark Penn Station", ny_departure + timedelta(minutes=18), 1),
            ("ED", "Edison", ed_departure, 5),  # Edison is intermediate
            ("TR", "Trenton", ed_departure + timedelta(minutes=30), 10),
        ]

        for code, name, dep_time, seq in stops_data:
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=seq,
                scheduled_departure=dep_time,
            )
            db_session.add(stop)

        await db_session.flush()

        # Create API response with correct origin (NY Penn at 7:20 PM)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3879",
            line_code="NE",
            destination="Trenton",
            stops=[
                builder.build_stop(
                    "NY",
                    "New York Penn Station",
                    ny_departure.strftime(NJT_TIME_FORMAT),
                ),
                builder.build_stop(
                    "NP",
                    "Newark Penn Station",
                    (ny_departure + timedelta(minutes=18)).strftime(NJT_TIME_FORMAT),
                ),
                builder.build_stop(
                    "ED", "Edison", ed_departure.strftime(NJT_TIME_FORMAT)
                ),
                builder.build_stop(
                    "TR",
                    "Trenton",
                    (ed_departure + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                ),
            ],
        )

        # Without the fix, this would return False (86 min > 10 min tolerance)
        # With the fix, it should return True (uses stops table departure)
        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is True, (
            "Journey should be recognized as same journey when stops table has "
            "correct origin even if journey.origin_station_code is stale"
        )

    @pytest.mark.asyncio
    async def test_still_detects_actual_mismatch(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that actual journey mismatches are still detected correctly.

        Scenario: Train ID reused for a completely different journey.
        - Journey 3879 originally NY → Trenton at 7:20 PM
        - Train ID reused for a new journey with different destination/time
        - Should correctly return False (different journey)
        """
        base_time = now_et().replace(hour=19, minute=20, second=0, microsecond=0)

        # Create journey for original run
        journey = TrainJourney(
            train_id="3879",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=base_time,
            has_complete_journey=True,
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # Create stops matching the journey
        stop = JourneyStop(
            journey_id=journey.id,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=base_time,
        )
        db_session.add(stop)
        await db_session.flush()

        # API response for a DIFFERENT journey (different destination)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3879",
            line_code="NE",
            destination="Long Branch",  # Different destination
            stops=[
                builder.build_stop(
                    "NY", "New York Penn Station", base_time.strftime(NJT_TIME_FORMAT)
                ),
            ],
        )

        # Should return False - different destination
        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is False, "Different destination should be detected as mismatch"

    @pytest.mark.asyncio
    async def test_correct_origin_still_works(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that journeys with correct origin_station_code still work.

        When origin_station_code matches first stop, the normal comparison should
        proceed using journey.scheduled_departure.
        """
        base_time = now_et().replace(hour=19, minute=20, second=0, microsecond=0)

        # Create journey with CORRECT origin
        journey = TrainJourney(
            train_id="3879",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",  # Correct
            terminal_station_code="TR",  # Correct
            data_source="NJT",
            scheduled_departure=base_time,  # Correct
            has_complete_journey=True,
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # Create matching stop
        stop = JourneyStop(
            journey_id=journey.id,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=base_time,
        )
        db_session.add(stop)
        await db_session.flush()

        # API response matching the journey
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3879",
            line_code="NE",
            destination="Trenton",
            stops=[
                builder.build_stop(
                    "NY", "New York Penn Station", base_time.strftime(NJT_TIME_FORMAT)
                ),
            ],
        )

        # Should return True - everything matches
        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is True, "Matching journey should be recognized"

    @pytest.mark.asyncio
    async def test_self_heals_when_journey_departure_drifts_from_stops(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that _is_same_journey() trusts the stops table even when
        origin_station_code is correct but journey.scheduled_departure has
        drifted.

        Scenario (the production bug seen for ~550 NJT trains/day):
        - Schedule collector iterates per-station schedules. NJT lists the
          same train in every stop-station's schedule, so the journey row's
          scheduled_departure gets overwritten with whichever station was
          processed last (e.g. the terminus arrival time, ~90 min off the
          actual NY origin departure).
        - origin_station_code stays correct ("NY") because schedule.py only
          assigns it on creation, not update.
        - Stops table is correct: stop_sequence=0 is NY at 21:35.
        - API returns first_stop=NY at 21:35.
        - Without fix: stored=23:05 vs api=21:35 = 5400s > 600s → falsely
          marked is_expired=True every collection cycle → train vanishes
          from /trains/departures.
        - With fix: stops table provides 21:35 → matches API → journey
          collector self-heals scheduled_departure via update_journey_metadata.
        """
        ny_departure = now_et().replace(hour=21, minute=35, second=0, microsecond=0)
        # Drifted journey time (e.g. terminus arrival), origin_station_code intact
        drifted_departure = ny_departure + timedelta(minutes=90)

        journey = TrainJourney(
            train_id="3889",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",  # CORRECT
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=drifted_departure,  # DRIFTED (the bug)
            has_complete_journey=True,
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # Stops table reflects the actual schedule
        ny_stop = JourneyStop(
            journey_id=journey.id,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=ny_departure,
        )
        db_session.add(ny_stop)
        await db_session.flush()

        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3889",
            line_code="NE",
            destination="Trenton -SEC",
            stops=[
                builder.build_stop(
                    "NY",
                    "New York Penn Station",
                    ny_departure.strftime(NJT_TIME_FORMAT),
                ),
                builder.build_stop(
                    "TR",
                    "Trenton",
                    (ny_departure + timedelta(minutes=90)).strftime(NJT_TIME_FORMAT),
                ),
            ],
        )

        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is True, (
            "Journey should self-heal via stops table when journey.scheduled_departure "
            "has drifted (the per-station schedule overwrite bug)"
        )

    @pytest.mark.asyncio
    async def test_incomplete_journey_skips_departure_check(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that incomplete journeys skip the departure time check.

        When has_complete_journey = False, the departure time mismatch should
        not cause rejection (allows journey correction to happen).
        """
        base_time = now_et().replace(hour=19, minute=20, second=0, microsecond=0)
        ed_departure = base_time + timedelta(minutes=86)

        # Create incomplete journey with stale origin
        journey = TrainJourney(
            train_id="3879",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="ED",  # Stale
            terminal_station_code="ED",  # Stale
            data_source="NJT",
            scheduled_departure=ed_departure,  # Stale
            has_complete_journey=False,  # Not yet complete
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # API response with correct origin
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3879",
            line_code="NE",
            destination="Trenton",
            stops=[
                builder.build_stop(
                    "NY", "New York Penn Station", base_time.strftime(NJT_TIME_FORMAT)
                ),
            ],
        )

        # Should return True - incomplete journey skips departure check
        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is True, "Incomplete journey should skip departure time check"

    @pytest.mark.asyncio
    async def test_uses_stops_table_when_origin_matches_but_journey_record_is_stale(
        self, db_session: AsyncSession, journey_collector
    ):
        """
        Test that when journey.origin_station_code matches the API's first stop
        but journey.scheduled_departure is stale relative to the stops table,
        _is_same_journey() uses the stops table's value rather than the stale
        journey-record value.

        Real-world scenario (NJT train 3943, 2026-05-06):
        - Train 3943 was scheduled NY -> Trenton departing 16:17 ET
        - At midnight schedule.py created the journey with the morning's schedule
          time but NJT returned null STOPS, so no stops were created
        - Discovery later (when the train showed up on station boards) created
          the NY stop with the current 16:17 schedule
        - journey.scheduled_departure remained at the original (stale) value
        - stops[NY].scheduled_departure has the correct 16:17 value
        - Every JIT collection attempt called getTrainStopList, which returned
          first_stop=NY at 16:17. _is_same_journey saw origin_station_code=NY ==
          first_stop=NY, so it used journey.scheduled_departure for comparison.
          The 26-minute gap exceeded the 10-min tolerance and the journey was
          falsely marked is_expired=True with api_error_count=99. JIT then
          short-circuited on is_expired and the user saw stale data with no
          track until the next discovery cycle reactivated the train.

        With the fix, _is_same_journey looks up the stop in our DB matching the
        API's first station (NY) and uses its scheduled_departure (16:17) for
        the comparison, correctly identifying this as the same journey. The
        subsequent update_journey_metadata then corrects journey.scheduled_departure
        to match the stops table.
        """
        base_time = now_et().replace(hour=16, minute=17, second=0, microsecond=0)
        # Stale value 26 minutes earlier than reality
        stale_journey_departure = base_time - timedelta(minutes=26)

        journey = TrainJourney(
            train_id="3943",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton -SEC",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=stale_journey_departure,  # STALE
            has_complete_journey=True,
            is_completed=False,
            observation_type="OBSERVED",
        )
        db_session.add(journey)
        await db_session.flush()

        # Stops table has the CORRECT (current) scheduled departure for NY
        stop = JourneyStop(
            journey_id=journey.id,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=base_time,  # Correct
        )
        db_session.add(stop)
        await db_session.flush()

        # API response with the same correct departure that the stops table has
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3943",
            line_code="NE",
            destination="Trenton",
            stops=[
                builder.build_stop(
                    "NY", "New York Penn Station", base_time.strftime(NJT_TIME_FORMAT)
                ),
            ],
        )

        result = await journey_collector._is_same_journey(
            db_session, journey, api_response
        )

        assert result is True, (
            "Same journey should be recognized when stops table agrees with API "
            "even though journey.scheduled_departure is stale"
        )
