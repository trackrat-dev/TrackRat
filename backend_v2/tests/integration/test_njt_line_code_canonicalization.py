"""
Integration tests for NJT line-code canonicalization at the write paths
(issue #1839), against real Postgres with real NJT API models.

NJT has three line vocabularies for the same train:
  - getTrainSchedule LINE: full names, one of which names TWO lines
    ("Main/Bergen County Line" -> MA for Bergen trains too);
  - real-time discovery LINE: short codes or abbreviated names;
  - getTrainStopList LINECODE: NJT's own codes ("ML", "BC", "GS", "MC").

Journey collection used to write LINECODE raw, so a Main Line train's OBSERVED
row became "ML" while its schedule-API twin kept "MA" — the departure board's
SCHEDULED/OBSERVED safety net keys on line code, never matched them, and the
board showed the train twice (once as "Train TBD").
"""

from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector, JourneyMatchResult
from trackrat.collectors.njt.schedule import NJTScheduleCollector
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


def _journey(
    *,
    train_id: str,
    line_code: str,
    observation_type: str,
    has_complete_journey: bool,
) -> TrainJourney:
    journey = TrainJourney(
        train_id=train_id,
        journey_date=DEPARTURE.date(),
        data_source="NJT",
        observation_type=observation_type,
        line_code=line_code,
        line_name="Main/Bergen County Line",
        destination="Suffern",
        origin_station_code="HB",
        terminal_station_code="SF",
        scheduled_departure=DEPARTURE,
        has_complete_journey=has_complete_journey,
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
    # Never called: every path under test receives its API data as an argument.
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
            ("MA", "BC", "BE"),  # Bergen train mislabeled by the schedule API
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
        journey = _journey(
            train_id="9147",
            line_code=stored,
            observation_type="OBSERVED",
            has_complete_journey=True,
        )
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


class TestScheduleLineCode:
    """NJTScheduleCollector resolves "Main/Bergen County Line" per train."""

    async def test_stop_list_linecode_resolves_main_bergen(
        self, db_session: AsyncSession, njt_client: NJTransitClient
    ) -> None:
        """The schedule API files Bergen train 2125 under "Main/Bergen County
        Line" (-> MA); its stop list's LINECODE "BC" says it is Bergen."""
        journey = _journey(
            train_id="2125",
            line_code="MA",
            observation_type="SCHEDULED",
            has_complete_journey=False,
        )
        db_session.add(journey)
        await db_session.flush()

        await NJTScheduleCollector(njt_client)._update_journey_with_stops(
            db_session, journey, _train_data("2125", "BC")
        )
        await db_session.flush()

        print(f"2125 after stop list: line_code={journey.line_code}")
        assert journey.line_code == "BE"
        assert journey.has_complete_journey is True

    @pytest.mark.parametrize(
        ("has_complete_journey", "expected"),
        [
            (True, "BE"),  # stop list already resolved it — keep
            (False, "MA"),  # nothing better known — schedule API's code
        ],
    )
    async def test_schedule_rerun_keeps_resolved_line_code(
        self,
        db_session: AsyncSession,
        njt_client: NJTransitClient,
        has_complete_journey: bool,
        expected: str,
    ) -> None:
        """Re-processing the schedule item must not put a resolved Bergen
        train back under Main."""
        db_session.add(
            _journey(
                train_id="2125",
                line_code="BE",
                observation_type="SCHEDULED",
                has_complete_journey=has_complete_journey,
            )
        )
        await db_session.flush()

        item = {
            "TRAIN_ID": "2125",
            "SCHED_DEP_DATE": DEPARTURE.strftime(NJT_TIME_FORMAT),
            "DESTINATION": "SUFFERN",
            "LINE": "Main/Bergen County Line",
            "TRACK": None,
        }
        result = await NJTScheduleCollector(njt_client)._process_schedule_item(
            db_session, item, "HB", "Hoboken", DEPARTURE.date()
        )
        await db_session.flush()

        journey = await db_session.scalar(
            select(TrainJourney).where(TrainJourney.train_id == "2125")
        )
        assert journey is not None
        print(
            f"complete={has_complete_journey} result={result} "
            f"line_code={journey.line_code}"
        )
        assert result == "updated"
        assert journey.line_code == expected
