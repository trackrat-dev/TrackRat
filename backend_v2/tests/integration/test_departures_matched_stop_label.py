"""
Integration test for DepartureService.get_departures ``label_matched_stop``
(cross-modal-hub endpoints, issue #1587 / PR #1593 review).

``from_station`` is expanded to its whole equivalence group before matching, so
a query for one WTC-complex platform code (``S138`` = WTC-Cortlandt, 1 train)
matches a train that physically boards at an *equivalent* platform (``SR25`` =
WTC-Cortlandt, R/W). By default the board echoes the requested ``S138``; with
``label_matched_stop=True`` it is relabeled to the actual matched stop ``SR25``.

This is the platform-mislabel the PR #1593 review found: the cross-modal-hub
trip search substitutes each of PWC's subway codes and dedupes the resulting
departures by ``(train_id, journey_date)``. Without matched-stop labeling every
substituted code produces a same-train duplicate under its own (wrong) label,
and the sorted-first ``S138`` wins the dedupe — surfacing the 1-train platform
for a train that actually runs on the R/W. ``label_matched_stop`` makes every
duplicate carry the real ``SR25`` platform so dedupe keeps the correct one.

The PostgreSQL-backed cases cover live journeys, future static GTFS, and the
same-day live/static merge without changing ordinary board presentation.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.config.stations import expand_station_codes
from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
    JourneyStop,
    TrainJourney,
)
from trackrat.services.departure import DepartureService
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET, now_et

SERVICE_DATE = date(2026, 7, 22)


async def _seed_gtfs_equivalent_platforms(
    db_session: AsyncSession, *, include_dedupe_trip: bool = False
) -> None:
    """Seed PWC, Penn, and Grand Central equivalent-platform GTFS trips."""
    route = GTFSRoute(
        data_source="SUBWAY",
        route_id="R",
        route_short_name="R",
        route_long_name="Broadway Local",
        route_color="FCCC0A",
    )
    db_session.add(route)
    await db_session.flush()
    db_session.add(
        GTFSCalendar(
            data_source="SUBWAY",
            service_id="EVERYDAY",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True,
            start_date=SERVICE_DATE - timedelta(days=1),
            end_date=SERVICE_DATE + timedelta(days=1),
        )
    )

    trip_stops: list[tuple[str, list[tuple[str, str | None, str | None]]]] = [
        (
            "pwc-out",
            [
                ("SR25", "12:00:00", "12:00:00"),
                ("S635", "12:12:00", "12:12:00"),
            ],
        ),
        (
            "pwc-in",
            [
                ("S635", "12:10:00", "12:10:00"),
                ("SR25", None, "12:22:00"),
            ],
        ),
        (
            "ny-gct",
            [
                ("SA28", "12:20:00", "12:20:00"),
                ("S723", "12:32:00", "12:32:00"),
                ("S901", "12:34:00", "12:34:00"),
            ],
        ),
    ]
    if include_dedupe_trip:
        trip_stops.append(
            (
                "dedupe",
                [
                    ("SR25", "12:30:00", "12:30:00"),
                    ("S635", "12:42:00", "12:42:00"),
                ],
            )
        )

    trips: list[tuple[GTFSTrip, list[tuple[str, str | None, str | None]]]] = []
    for trip_id, stops in trip_stops:
        trip = GTFSTrip(
            data_source="SUBWAY",
            trip_id=trip_id,
            route_id=route.id,
            service_id="EVERYDAY",
            trip_headsign="Forest Hills",
            train_id=trip_id,
            direction_id=0,
        )
        db_session.add(trip)
        trips.append((trip, stops))
    await db_session.flush()

    for trip, stops in trips:
        for sequence, (station_code, arrival_time, departure_time) in enumerate(
            stops, start=1
        ):
            db_session.add(
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=sequence,
                    gtfs_stop_id=station_code,
                    station_code=station_code,
                    arrival_time=arrival_time,
                    departure_time=departure_time,
                )
            )
    await db_session.flush()


def _make_observed_dedupe_journey(fixed_now: datetime) -> TrainJourney:
    departure = ET.localize(datetime.combine(SERVICE_DATE, time(12, 30)))
    journey = TrainJourney(
        train_id="SR-dedupe",
        journey_date=SERVICE_DATE,
        data_source="SUBWAY",
        line_code="R",
        line_name="R",
        line_color="#FCCC0A",
        destination="Forest Hills",
        origin_station_code="SR25",
        terminal_station_code="S635",
        scheduled_departure=departure,
        first_seen_at=fixed_now - timedelta(minutes=5),
        last_updated_at=fixed_now - timedelta(minutes=1),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code="SR25",
            station_name="Cortlandt St",
            scheduled_departure=departure,
            stop_sequence=0,
            track="2",
            has_departed_station=False,
        ),
        JourneyStop(
            station_code="S635",
            station_name="14 St-Union Sq",
            scheduled_arrival=departure + timedelta(minutes=12),
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


def _make_rw_journey() -> TrainJourney:
    """An R/W subway train boarding at SR25 (WTC-Cortlandt) -> S635 (Union Sq)."""
    departure = now_et() + timedelta(minutes=8)
    arrival = departure + timedelta(minutes=12)
    journey = TrainJourney(
        train_id="R100",
        journey_date=departure.date(),
        data_source="SUBWAY",
        line_code="R",
        line_name="R",
        line_color="#FCCC0A",
        destination="Astoria-Ditmars Blvd",
        origin_station_code="SR25",
        terminal_station_code="S635",
        scheduled_departure=departure,
        first_seen_at=now_et() - timedelta(minutes=5),
        last_updated_at=now_et() - timedelta(minutes=1),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code="SR25",
            station_name="Cortlandt St",
            scheduled_departure=departure,
            stop_sequence=0,
            has_departed_station=False,
        ),
        JourneyStop(
            station_code="S635",
            station_name="14 St-Union Sq",
            scheduled_arrival=arrival,
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


@pytest.mark.asyncio
class TestDeparturesMatchedStopLabel:
    """DepartureService.get_departures label_matched_stop behavioral coverage."""

    async def test_matched_stop_relabels_boarding_to_real_platform(
        self, db_session: AsyncSession
    ):
        # Precondition: the queried code and the real platform are distinct but
        # equivalent — otherwise the test would prove nothing.
        assert "SR25" in expand_station_codes("S138")
        assert "S138" != "SR25"

        db_session.add(_make_rw_journey())
        await db_session.commit()
        service = DepartureService()

        labeled = await service.get_departures(
            db_session,
            "S138",  # WTC-Cortlandt (1 train) — an equivalent, not the platform
            "S635",
            data_sources=["SUBWAY"],
            skip_gtfs_merge=True,
            skip_individual_refresh=True,
            label_matched_stop=True,
        )

        assert len(labeled.departures) == 1, (
            "the R/W train must be matched via the WTC equivalence group; got "
            f"{[d.departure.code for d in labeled.departures]}"
        )
        dep = labeled.departures[0]
        assert dep.departure.code == "SR25", (
            "label_matched_stop must surface the actual boarding platform "
            f"(SR25), not the requested equivalent S138; got {dep.departure.code}"
        )
        assert dep.departure.name == "Cortlandt St"
        assert dep.arrival is not None and dep.arrival.code == "S635"

    async def test_default_echoes_requested_code(self, db_session: AsyncSession):
        """Without the flag the board echoes the requested code (unchanged
        behavior for every existing caller)."""
        db_session.add(_make_rw_journey())
        await db_session.commit()
        service = DepartureService()

        echoed = await service.get_departures(
            db_session,
            "S138",
            "S635",
            data_sources=["SUBWAY"],
            skip_gtfs_merge=True,
            skip_individual_refresh=True,
        )

        assert len(echoed.departures) == 1
        dep = echoed.departures[0]
        assert dep.departure.code == "S138", (
            "default labeling must echo the requested from_station; got "
            f"{dep.departure.code}"
        )

    async def test_future_gtfs_labels_actual_equivalent_platforms(
        self, db_session: AsyncSession
    ) -> None:
        GTFSService._service_id_cache.clear()
        await _seed_gtfs_equivalent_platforms(db_session)
        await db_session.commit()
        fixed_now = ET.localize(
            datetime.combine(SERVICE_DATE - timedelta(days=1), time(9))
        )
        service = DepartureService()

        with patch("trackrat.services.departure.now_et", return_value=fixed_now):
            pwc_out = await service.get_departures(
                db_session,
                "S138",
                "S635",
                date=SERVICE_DATE,
                data_sources=["SUBWAY"],
                label_matched_stop=True,
            )
            pwc_in = await service.get_departures(
                db_session,
                "S635",
                "S138",
                date=SERVICE_DATE,
                data_sources=["SUBWAY"],
                label_matched_stop=True,
            )
            ny_to_gct = await service.get_departures(
                db_session,
                "S128",
                "S631",
                date=SERVICE_DATE,
                data_sources=["SUBWAY"],
                label_matched_stop=True,
            )
            ordinary = await service.get_departures(
                db_session,
                "S128",
                "S631",
                date=SERVICE_DATE,
                data_sources=["SUBWAY"],
            )

        assert pwc_out.departures[0].departure.code == "SR25"
        assert pwc_out.departures[0].arrival is not None
        assert pwc_out.departures[0].arrival.code == "S635"
        assert pwc_in.departures[0].departure.code == "S635"
        assert pwc_in.departures[0].arrival is not None
        assert pwc_in.departures[0].arrival.code == "SR25"
        assert pwc_in.departures[0].arrival.scheduled_time is not None
        assert pwc_in.departures[0].arrival.scheduled_time.minute == 22
        assert ny_to_gct.departures[0].departure.code == "SA28"
        assert ny_to_gct.departures[0].arrival is not None
        assert ny_to_gct.departures[0].arrival.code == "S723"
        assert ordinary.departures[0].departure.code == "S128"
        assert ordinary.departures[0].arrival is not None
        assert ordinary.departures[0].arrival.code == "S631"

    async def test_same_day_gtfs_labels_both_directions_and_dedup_keeps_live_platform(
        self, db_session: AsyncSession
    ) -> None:
        fixed_now = ET.localize(datetime.combine(SERVICE_DATE, time(11)))
        GTFSService._service_id_cache.clear()
        await _seed_gtfs_equivalent_platforms(db_session, include_dedupe_trip=True)
        db_session.add(_make_observed_dedupe_journey(fixed_now))
        await db_session.commit()
        service = DepartureService()

        with patch("trackrat.services.departure.now_et", return_value=fixed_now):
            pwc_out = await service.get_departures(
                db_session,
                "S138",
                "S635",
                data_sources=["SUBWAY"],
                skip_individual_refresh=True,
                label_matched_stop=True,
            )
            pwc_in = await service.get_departures(
                db_session,
                "S635",
                "S138",
                data_sources=["SUBWAY"],
                skip_individual_refresh=True,
                label_matched_stop=True,
            )

        outbound = {departure.train_id: departure for departure in pwc_out.departures}
        assert outbound["SR-pwc-out"].departure.code == "SR25"
        assert outbound["SR-pwc-out"].observation_type == "SCHEDULED"
        assert outbound["SR-dedupe"].departure.code == "SR25"
        assert outbound["SR-dedupe"].departure.track == "2"
        assert outbound["SR-dedupe"].observation_type == "OBSERVED"
        assert [d.train_id for d in pwc_out.departures].count("SR-dedupe") == 1
        assert pwc_in.departures[0].departure.code == "S635"
        assert pwc_in.departures[0].arrival is not None
        assert pwc_in.departures[0].arrival.code == "SR25"
