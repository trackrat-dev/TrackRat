"""
Integration tests (real Postgres) for NJT GTFS train numbers (issue #1839).

NJT's GTFS bundle has no trip_short_name and digit-free headsigns, so every
NJT GTFS trip used to take its internal trip_id as its train number. The
rider-facing train number is the trip's block_id on commuter-rail routes. The
rows below are copied verbatim from NJT's published rail_data.zip
(last-modified 2026-09-17), including the two production pairs that showed
twice on 2026-10-03 boards:

  trip_id 2036 (block 1881)  Hoboken 19:16 -> Waldwick, Main/Bergen (MNBN)
  trip_id 4008 (block 7269)  NY Penn 19:07 -> Long Branch, NJCL

and the three block shapes that must NOT become train numbers: a light-rail
block ("342JC203"), a numeric light-rail vehicle block (River Line "6"), and a
bus substitution on a rail route ("PJBUS").
"""

import importlib
import io
import zipfile
from datetime import date, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from trackrat.models.api import TrainDeparture
from trackrat.models.database import GTFSTrip, JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET

SERVICE_DATE = date(2026, 10, 3)

NJT_ROUTES = (
    "route_id,agency_id,route_short_name,route_long_name,route_type,route_url,route_color\n"
    '4,"NJT","HBLR","Hudson-Bergen Light Rail",0,"",F79620\n'
    '5,"NJT","MNBN","Main/Bergen County Line",2,"",FFD411\n'
    '6,"NJT","MNBNP","Port Jervis Line",2,"",F7F7F7\n'
    '11,"NJT","NJCL","North Jersey Coast Line",2,"",03A3DF\n'
    '17,"NJT","RVLN","Riverline Light Rail",0,"",F79620\n'
)
NJT_TRIPS = (
    "route_id,service_id,trip_id,trip_headsign,direction_id,block_id,shape_id\n"
    '5,1,2036,"WALDWICK",1,"1881",617\n'
    '11,1,4008,"LONG BRANCH",1,"7269",2502\n'
    '4,1,363,"HBLR HOBOKEN TERMINAL",0,"342JC203",363\n'
    '17,1,6111,"RvLN CAMDEN",0,"6",3788\n'
    '6,1,2216,"HOBOKEN",0,"PJBUS",797\n'
)
NJT_STOPS = (
    "stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id\n"
    '63,95063,"HOBOKEN",,40.734843,-74.028046,336\n'
    '38174,95167,"SECAUCUS LOWER LEVEL",,40.761188,-74.075821,333\n'
    '105,95105,"NEW YORK PENN STATION",,40.750046,-73.992358,329\n'
    '38187,95168,"SECAUCUS UPPER LEVEL",,40.761188,-74.075821,329\n'
    '36998,30837,"LIBERTY STATE PARK-RIDE LIGHT RAIL STA",,40.710378,-74.055812,336\n'
    '36997,30836,"JERSEY AVENUE LIGHT RAIL STATION",,40.714978,-74.048491,336\n'
    '38291,30855,"TRENTON TRANSIT CENTER LIGHT RAIL STATION",,40.218348,-74.755194,336\n'
    '38292,30856,"HAMILTON AVENUE LIGHT RAIL STATION",,40.211928,-74.755882,336\n'
    '123,95123,"PORT JERVIS",,41.374899,-74.694622,6477\n'
    '86,95086,"MIDDLETOWN NY",,41.457488,-74.370390,5965\n'
)
NJT_STOP_TIMES = (
    "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type,shape_dist_traveled\n"
    "2036,19:16:00,19:16:00,63,1,0,0,0\n"
    "2036,19:27:00,19:27:00,38174,2,0,0,3.9\n"
    "4008,19:07:00,19:07:00,105,1,0,0,0\n"
    "4008,19:16:00,19:16:00,38187,2,0,0,3.5\n"
    "363,05:20:00,05:20:00,36998,1,0,0,0\n"
    "363,05:23:00,05:23:00,36997,2,0,0,0.8\n"
    "6111,06:27:00,06:27:00,38291,1,0,0,0\n"
    "6111,06:29:00,06:29:00,38292,2,0,0,0.6\n"
    "2216,04:24:00,04:24:00,123,1,0,0,0\n"
    "2216,04:54:00,04:54:00,86,2,0,0,18.2\n"
)


def _njt_bundle() -> bytes:
    """NJT-shaped bundle: calendar_dates only, no calendar.txt (as NJT ships)."""
    files = {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            'NJT,"NJ TRANSIT RAIL",http://www.njtransit.com,America/New_York\n'
        ),
        "routes.txt": NJT_ROUTES,
        "calendar_dates.txt": "service_id,date,exception_type\n1,20261003,1\n",
        "stops.txt": NJT_STOPS,
        "trips.txt": NJT_TRIPS,
        "stop_times.txt": NJT_STOP_TIMES,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buffer.getvalue()


@pytest.fixture
async def parsed_njt(db_session: AsyncSession) -> GTFSService:
    service = GTFSService()
    stats = await service._parse_and_store_gtfs(
        db_session, "NJT", _njt_bundle(), today=SERVICE_DATE
    )
    print(f"parse stats: {stats}")
    assert stats["trips"] == 5
    return service


class TestNjtGtfsTrainNumbers:
    async def test_rail_trips_take_block_id_as_train_number(
        self, db_session: AsyncSession, parsed_njt: GTFSService
    ) -> None:
        rows = (
            await db_session.execute(
                select(GTFSTrip.trip_id, GTFSTrip.train_id).where(
                    GTFSTrip.data_source == "NJT"
                )
            )
        ).all()
        train_ids = dict(rows)
        print(f"trip_id -> train_id: {train_ids}")

        # Commuter rail: block_id is the real-time train number
        assert train_ids["2036"] == "1881"
        assert train_ids["4008"] == "7269"
        # Light-rail blocks (vehicle ids, numeric or not) and bus
        # substitutions never become train numbers
        assert train_ids["363"] is None
        assert train_ids["6111"] is None
        assert train_ids["2216"] is None

    async def test_departure_board_shows_real_train_number(
        self, db_session: AsyncSession, parsed_njt: GTFSService
    ) -> None:
        response = await parsed_njt.get_scheduled_departures(
            db_session, "HB", "TS", SERVICE_DATE, data_sources=["NJT"]
        )

        trains = [(d.train_id, d.line.code) for d in response.departures]
        print(f"HB -> TS GTFS departures: {trains}")
        assert trains == [("1881", "MA")]

    async def test_gtfs_twin_merges_with_realtime_train_by_number(
        self, db_session: AsyncSession, parsed_njt: GTFSService
    ) -> None:
        """Production HB 19:16, 2026-10-03: real-time Bergen 1881 ("BE")
        beside its GTFS trip. With the scheduled minute republished three
        minutes late, the line + time fallback (±1 min on each side) cannot
        pair them — the train number must."""
        response = await parsed_njt.get_scheduled_departures(
            db_session, "HB", "TS", SERVICE_DATE, data_sources=["NJT"]
        )
        gtfs_departure = response.departures[0]
        realtime: TrainDeparture = gtfs_departure.model_copy(
            update={
                "train_id": "1881",
                "line": gtfs_departure.line.model_copy(update={"code": "BE"}),
                "observation_type": "OBSERVED",
                "departure": gtfs_departure.departure.model_copy(
                    update={
                        "scheduled_time": ET.localize(datetime(2026, 10, 3, 19, 19))
                    }
                ),
            }
        )

        service = DepartureService.__new__(DepartureService)
        merged = service._merge_departures(realtime=[realtime], gtfs=[gtfs_departure])

        kept = [(d.train_id, d.line.code, d.observation_type) for d in merged]
        print(f"merged: {kept}")
        assert kept == [("1881", "BE", "OBSERVED")]

    async def test_train_details_by_real_number_and_by_old_trip_id(
        self, db_session: AsyncSession, parsed_njt: GTFSService
    ) -> None:
        by_number = await parsed_njt.get_train_details(
            db_session, "1881", SERVICE_DATE, "NJT"
        )
        by_trip_id = await parsed_njt.get_train_details(
            db_session, "2036", SERVICE_DATE, "NJT"
        )

        assert by_number is not None and by_trip_id is not None
        print(
            f"by number: {by_number.train_id} {by_number.route.origin_code}; "
            f"by trip_id: {by_trip_id.train_id}"
        )
        assert by_number.train_id == "1881"
        assert by_number.route.origin_code == "HB"
        # A link minted before the fix (trip_id) still resolves, now to the
        # real number
        assert by_trip_id.train_id == "1881"


phantom_migration = importlib.import_module(
    "trackrat.db.migrations.versions."
    "20261004_0106-6f2d7f054922_delete_njt_journeys_materialized_under_"
)


def _run_phantom_upgrade(session: Session) -> None:
    context = MigrationContext.configure(session.connection())
    with Operations.context(context):
        phantom_migration.upgrade()


def _journey(
    train_id: str,
    journey_date: date,
    *,
    data_source: str = "NJT",
    observation_type: str = "SCHEDULED",
    cancellation_reason: str | None = "Not observed in real-time feed",
) -> TrainJourney:
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        line_code="MA",
        destination="HOBOKEN",
        origin_station_code="WK",
        terminal_station_code="HB",
        data_source=data_source,
        observation_type=observation_type,
        scheduled_departure=ET.localize(
            datetime.combine(journey_date, datetime.min.time()).replace(hour=12)
        ),
        has_complete_journey=False,
        is_cancelled=cancellation_reason is not None,
        cancellation_reason=cancellation_reason,
    )
    journey.stops = [
        JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            stop_sequence=0,
            scheduled_arrival=journey.scheduled_departure,
        )
    ]
    return journey


class TestDeletePhantomMaterializedJourneys:
    async def test_deletes_phantoms_and_their_stops(
        self, db_session: AsyncSession
    ) -> None:
        phantoms = [
            _journey("2938", date(2026, 9, 22)),
            _journey("1920", date(2026, 10, 1)),
        ]
        db_session.add_all(phantoms)
        await db_session.flush()
        phantom_ids = [j.id for j in phantoms]

        await db_session.run_sync(_run_phantom_upgrade)

        db_session.expire_all()
        journeys = (
            await db_session.scalars(
                select(TrainJourney.id).where(TrainJourney.id.in_(phantom_ids))
            )
        ).all()
        stops = (
            await db_session.scalars(
                select(JourneyStop.id).where(JourneyStop.journey_id.in_(phantom_ids))
            )
        ).all()
        print(f"remaining journeys {journeys}, stops {stops}")
        assert journeys == [] and stops == []

    @pytest.mark.parametrize(
        ("label", "journey_kwargs"),
        [
            ("real train took the row", {"observation_type": "OBSERVED"}),
            ("not swept as unobserved", {"cancellation_reason": None}),
            ("same number, other date", {"journey_date": date(2026, 10, 2)}),
            ("same key, other source", {"data_source": "AMTRAK"}),
        ],
    )
    async def test_leaves_every_other_row(
        self, db_session: AsyncSession, label: str, journey_kwargs: dict
    ) -> None:
        journey_date = journey_kwargs.pop("journey_date", date(2026, 10, 1))
        journey = _journey("1920", journey_date, **journey_kwargs)
        db_session.add(journey)
        await db_session.flush()
        journey_id = journey.id

        await db_session.run_sync(_run_phantom_upgrade)

        db_session.expire_all()
        remaining = await db_session.scalar(
            select(TrainJourney.id).where(TrainJourney.id == journey_id)
        )
        print(f"{label}: remaining id {remaining}")
        assert remaining == journey_id
