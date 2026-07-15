"""
Unit tests for track sanitization in the NJT schedule collector (issue #1508).

schedule.py wrote raw NJT TRACK values into String(5) columns at three
sites (journey discovery_track, placeholder-stop track, nightly stop-list
track), bypassing utils/sanitize.sanitize_track — which journey.py and
discovery.py already use, and whose own doctest ("Millstone Running" ->
"Mill+") proves the API serves >5-char values. A raw write raises
StringDataRightTruncation at flush: the schedule item (or the train's whole
stop list, in the once-daily stop pass) fails, leaving the journey
invisible in route searches until real-time collection repairs it.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.njt_api_responses import (
    NJT_TIME_FORMAT,
    StopBuilder,
    create_stop_list_response,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture
def mock_njt_client():
    return AsyncMock(spec=NJTransitClient)


@pytest.fixture
def schedule_collector(mock_njt_client):
    return NJTScheduleCollector(mock_njt_client)


class TestScheduleTrackSanitization:
    @pytest.mark.asyncio
    async def test_schedule_item_with_long_track_is_sanitized_not_failed(
        self, db_session: AsyncSession, schedule_collector
    ):
        """A schedule item carrying a >5-char TRACK must create its journey
        with a sanitized track instead of failing on String(5) overflow.
        """
        departure = now_et().replace(second=0, microsecond=0) + timedelta(hours=2)

        schedule_data = [
            {
                "STATION_2CHAR": "NY",
                "STATIONNAME": "New York Penn",
                "ITEMS": [
                    {
                        "TRAIN_ID": "9101",
                        "SCHED_DEP_DATE": departure.strftime(NJT_TIME_FORMAT),
                        "DESTINATION": "Trenton",
                        "LINE": "Northeast Corridor",
                        "TRACK": "Millstone Running",  # >5 chars, real NJT value
                    }
                ],
            }
        ]

        stats = await schedule_collector._process_schedule_data(
            db_session, schedule_data
        )

        assert stats["errors"] == 0, (
            "A long TRACK value must be sanitized, not error the item "
            f"(stats: {stats})"
        )
        assert stats["new_schedules"] == 1

        journey = await db_session.scalar(
            select(TrainJourney).where(
                TrainJourney.train_id == "9101",
                TrainJourney.data_source == "NJT",
            )
        )
        assert journey is not None
        assert journey.discovery_track == "Mill+", (
            "discovery_track must be the sanitize_track() output, matching "
            "journey.py/discovery.py behavior"
        )

        stop = await db_session.scalar(
            select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        )
        assert stop is not None
        assert stop.track == "Mill+"
        assert stop.track_assigned_at is not None

    @pytest.mark.asyncio
    async def test_stop_list_with_long_track_is_sanitized_not_failed(
        self, db_session: AsyncSession, schedule_collector, mock_njt_client
    ):
        """The nightly stop-list pass must sanitize per-stop TRACK values —
        one overflowing stop previously aborted the train's entire stop list
        for the day.
        """
        departure = now_et().replace(second=0, microsecond=0) + timedelta(hours=2)

        journey = TrainJourney(
            train_id="9102",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=departure,
            has_complete_journey=False,
            stops_count=0,
        )
        db_session.add(journey)
        await db_session.flush()

        builder = StopBuilder()
        mock_njt_client.get_train_stop_list.return_value = create_stop_list_response(
            train_id="9102",
            line_code="NE",
            destination="Trenton",
            stops=[
                builder.build_stop(
                    "NY",
                    "New York Penn",
                    departure.strftime(NJT_TIME_FORMAT),
                    track="Millstone Running",  # >5 chars
                ),
                builder.build_stop(
                    "TR",
                    "Trenton",
                    (departure + timedelta(minutes=75)).strftime(NJT_TIME_FORMAT),
                ),
            ],
        )

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            db_session
        )

        assert stats["stop_collections_failed"] == 0, (
            "A >5-char TRACK on one stop must not abort the train's stop "
            f"list (stats: {stats})"
        )
        assert stats["stop_collections_successful"] == 1

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
        assert len(stops) == 2
        assert stops[0].track == "Mill+"
        assert stops[1].track is None
