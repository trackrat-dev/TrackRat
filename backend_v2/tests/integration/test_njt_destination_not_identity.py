"""
Integration tests: a differing NJT destination never expires a live train
(issue #1878), against real Postgres with real NJT API models.

Journey collection used to treat any difference between the stored destination
and getTrainStopList's DESTINATION as "a different journey under this train_id"
and expire the row. NJT spells the same terminal differently across its APIs
("Newark Penn" vs "Newark Penn Station") and genuinely changes a running
train's destination (diversions to Hoboken), so live trains were expired, then
reactivated by discovery and re-expired by the next collection all day. While
expired a train is dropped from the departure board and blocked from JIT.
Identity is now decided by the scheduled origin departure alone, and the API's
destination is adopted in place.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et

NJT_TIME_FORMAT = "%d-%b-%Y %I:%M:%S %p"

# (stored destination, getTrainStopList DESTINATION) pairs from the production
# and staging `journey_mismatch_destination` logs quoted in issue #1878.
SPELLING_VARIANTS = [
    ("Newark Penn", "Newark Penn Station"),
    ("Newark Penn &#9992", "Newark Penn Station"),
    ("Newark Penn", "Newark Penn with connecting service to Long Branch"),
    ("Atlantic City", "Atlantic City Rail Terminal"),
    ("Jersey Ave", "Jersey Avenue"),
    ("Jersey Ave -SEC &#9992", "Jersey Avenue"),
    ("Jersey Ave.", "Jersey Avenue"),
    ("Long Branch", "Long Branch with connecting service to Bay Head"),
    ("Long Branch-BH &#9992", "Long Branch with connecting service to Bay Head"),
    ("Long Branch", "Long Branch with connecting service to Penn Station New York"),
    (
        "Long Branch-NY &#9992",
        "Long Branch with connecting service to Penn Station New York",
    ),
    ("Matawan-BH &#9992", "Matawan with connecting service to Bay Head"),
    ("Secaucus Lower Lvl", "Secaucus Transfer"),
    ("Secaucus Upper Lvl", "Secaucus"),
    ("Lk Hopatcong", "Lake Hopatcong"),
    ("So. Amboy", "South Amboy"),
    ("MSU", "Montclair State"),
    ("Princeton Junction", "Princeton Jct."),
    ("TRENTON TRANSIT CENTER", "Trenton"),
]
REAL_DESTINATION_CHANGES = [
    ("Philadelphia", "North Phil"),
    ("New York", "Hoboken"),
    ("New York -SEC", "Hoboken"),
    ("Waldwick", "Suffern"),
    ("Suffern", "Port Jervis"),
    ("Port Jervis", "Campbell Hall"),
    ("Spring Valley", "Essex Street"),
]


def _fmt(at: datetime) -> str:
    return at.strftime(NJT_TIME_FORMAT)


Stops = list[tuple[str, str, datetime]]


@pytest.fixture
def stops() -> Stops:
    """Raritan Valley short-turn RA -> DN -> NP, all stops still ahead, so the
    collection neither infers departures nor completes the journey. Built when
    the test runs, not at import, so a long suite can't age them into the past.
    """
    ra_departure = now_et().replace(second=0, microsecond=0) + timedelta(minutes=10)
    return [
        ("RA", "Raritan", ra_departure),
        ("DN", "Dunellen", ra_departure + timedelta(minutes=20)),
        ("NP", "Newark Penn Station", ra_departure + timedelta(minutes=45)),
    ]


def _train_data(destination: str, stops: Stops) -> NJTransitTrainData:
    """getTrainStopList response for train 5528 bound for ``destination``."""
    return NJTransitTrainData(
        TRAIN_ID="5528",
        LINECODE="RV",
        BACKCOLOR="#FAA634",
        FORECOLOR="black",
        SHADOWCOLOR="black",
        DESTINATION=destination,
        STOPS=[
            NJTransitStopData(
                STATION_2CHAR=code,
                STATIONNAME=name,
                TIME=_fmt(at),
                DEP_TIME=_fmt(at),
                SCHED_ARR_DATE=_fmt(at),
                SCHED_DEP_DATE=_fmt(at),
            )
            for code, name, at in stops
        ],
    )


def _journey(destination: str, stops: Stops) -> TrainJourney:
    """OBSERVED journey as discovery/schedule left it, with ``destination``."""
    ra_departure = stops[0][2]
    journey = TrainJourney(
        train_id="5528",
        journey_date=ra_departure.date(),
        data_source="NJT",
        observation_type="OBSERVED",
        line_code="RV",
        line_name="Raritan Valley Line",
        destination=destination,
        origin_station_code="RA",
        terminal_station_code="NP",
        scheduled_departure=ra_departure,
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
        api_error_count=0,
    )
    journey.stops = [
        JourneyStop(
            station_code=code,
            station_name=name,
            scheduled_departure=at,
            scheduled_arrival=at,
            stop_sequence=sequence,
        )
        for sequence, (code, name, at) in enumerate(stops)
    ]
    return journey


@pytest.fixture
async def njt_client() -> AsyncGenerator[NJTransitClient, None]:
    # Never called: collection receives its API data via prefetched_train_data.
    client = NJTransitClient()
    try:
        yield client
    finally:
        await client.close()


async def _collect(
    db_session: AsyncSession,
    njt_client: NJTransitClient,
    stops: Stops,
    stored: str,
    api: str,
) -> TrainJourney:
    journey = _journey(stored, stops)
    db_session.add(journey)
    await db_session.flush()

    await JourneyCollector(njt_client).collect_journey_details(
        db_session,
        journey,
        skip_enhancement=True,
        prefetched_train_data=_train_data(api, stops),
    )
    await db_session.refresh(journey)
    print(
        f"stored={stored!r} api={api!r} -> destination={journey.destination!r} "
        f"is_expired={journey.is_expired} api_error_count={journey.api_error_count}"
    )
    return journey


class TestDestinationIsNotIdentity:
    """collect_journey_details never expires a train over its destination."""

    @pytest.mark.parametrize(
        ("stored", "api"), SPELLING_VARIANTS + REAL_DESTINATION_CHANGES
    )
    async def test_collection_keeps_train_live_and_adopts_api_destination(
        self,
        db_session: AsyncSession,
        njt_client: NJTransitClient,
        stops: Stops,
        stored: str,
        api: str,
    ) -> None:
        journey = await _collect(db_session, njt_client, stops, stored, api)

        assert journey.is_expired is False, (
            f"Destination {stored!r} -> {api!r} with a matching scheduled "
            "departure is the same train and must not expire it"
        )
        assert journey.api_error_count == 0, (
            f"Destination {stored!r} -> {api!r} must not count as a strike "
            f"(api_error_count={journey.api_error_count})"
        )
        assert journey.destination == api, (
            f"Collection must adopt the API's destination {api!r}, "
            f"row still says {journey.destination!r}"
        )

    async def test_live_train_stays_on_departure_board(
        self, db_session: AsyncSession, njt_client: NJTransitClient, stops: Stops
    ) -> None:
        """The reported case: 5528 stored as "Newark Penn" while
        getTrainStopList says "Newark Penn Station". The DN -> NP board must
        list the live OBSERVED journey, not drop it as expired."""
        await _collect(
            db_session, njt_client, stops, "Newark Penn", "Newark Penn Station"
        )

        response = await DepartureService().get_departures(
            db=db_session,
            from_station="DN",
            to_station="NP",
            time_from=now_et() - timedelta(minutes=5),
            time_to=now_et() + timedelta(hours=2),
            skip_inline_refresh=True,
            skip_gtfs_merge=True,
        )

        board = [
            (d.train_id, d.observation_type, d.destination, d.is_expired)
            for d in response.departures
        ]
        print(f"DN -> NP board: {board}")
        assert board == [("5528", "OBSERVED", "Newark Penn Station", False)], (
            "Train 5528 must stay on the DN -> NP board as a live OBSERVED "
            f"departure after collection, got {board}"
        )
