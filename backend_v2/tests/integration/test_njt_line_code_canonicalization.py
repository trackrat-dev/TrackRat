"""
Integration tests for NJT line-code canonicalization at the write paths
(issue #1839), against real Postgres with real NJT API models.

Journey collection used to write getTrainStopList's LINECODE raw — NJT's own
codes ("ML", "BC", "GS", "MC") — so a Main Line train's OBSERVED row carried
"ML" while the GTFS timetable departure for the same train carried "MA". The
departure board pairs NJT GTFS departures with real-time ones by line code and
time (NJT GTFS uses different train numbers), so the two never matched and the
board showed the train twice, once as "Train TBD".
"""

from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector, JourneyMatchResult
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

NJT_TIME_FORMAT = "%d-%b-%Y %I:%M:%S %p"
DEPARTURE = now_et().replace(hour=12, minute=39, second=0, microsecond=0)


def _train_data(train_id: str, linecode: str) -> NJTransitTrainData:
    """getTrainStopList response for a Hoboken -> Suffern train."""
    return NJTransitTrainData(
        TRAIN_ID=train_id,
        LINECODE=linecode,
        BACKCOLOR="#FFCF01",
        FORECOLOR="black",
        SHADOWCOLOR="black",
        DESTINATION="Suffern",
        STOPS=[
            NJTransitStopData(
                STATION_2CHAR="HB",
                STATIONNAME="Hoboken",
                TIME=DEPARTURE.strftime(NJT_TIME_FORMAT),
                DEP_TIME=DEPARTURE.strftime(NJT_TIME_FORMAT),
                SCHED_DEP_DATE=DEPARTURE.strftime(NJT_TIME_FORMAT),
            ),
            NJTransitStopData(
                STATION_2CHAR="SF",
                STATIONNAME="Suffern",
                TIME=(DEPARTURE + timedelta(minutes=70)).strftime(NJT_TIME_FORMAT),
                SCHED_ARR_DATE=(DEPARTURE + timedelta(minutes=70)).strftime(
                    NJT_TIME_FORMAT
                ),
            ),
        ],
    )


def _journey(*, train_id: str, line_code: str) -> TrainJourney:
    """OBSERVED NJT journey as discovery leaves it before journey collection."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=DEPARTURE.date(),
        data_source="NJT",
        observation_type="OBSERVED",
        line_code=line_code,
        line_name="Main Line",
        destination="Suffern",
        origin_station_code="HB",
        terminal_station_code="SF",
        scheduled_departure=DEPARTURE,
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            scheduled_departure=DEPARTURE,
            stop_sequence=0,
        )
    ]
    return journey


@pytest.fixture
async def njt_client() -> AsyncGenerator[NJTransitClient, None]:
    # Never called: _is_same_journey receives its API data as an argument.
    client = NJTransitClient()
    try:
        yield client
    finally:
        await client.close()


class TestJourneyCollectionLineCode:
    """JourneyCollector._is_same_journey heals line_code from LINECODE."""

    @pytest.mark.parametrize(
        ("stored", "linecode", "expected"),
        [
            ("MA", "ML", "MA"),  # Main Line: NJT's code must not replace ours
            ("MA", "BC", "BE"),  # NJT's LINECODE is authoritative for the line
            ("BE", "BC", "BE"),
            ("GL", "GS", "GL"),
            ("MO", "MC", "MO"),
            ("No", "NC", "NC"),
        ],
    )
    async def test_linecode_is_canonicalized(
        self,
        db_session: AsyncSession,
        njt_client: NJTransitClient,
        stored: str,
        linecode: str,
        expected: str,
    ) -> None:
        journey = _journey(train_id="9147", line_code=stored)
        db_session.add(journey)
        await db_session.flush()

        result = await JourneyCollector(njt_client)._is_same_journey(
            db_session, journey, _train_data("9147", linecode)
        )

        print(f"stored={stored} LINECODE={linecode} -> {journey.line_code}")
        assert result is JourneyMatchResult.MATCH
        assert journey.line_code == expected, (
            f"LINECODE {linecode!r} on a {stored!r} row produced "
            f"{journey.line_code!r}, expected {expected!r}"
        )
