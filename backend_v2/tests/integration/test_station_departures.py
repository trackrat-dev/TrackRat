"""Integration tests for the single-station upcoming departure board (issue #1441).

The web app's per-station board (`/station/:code`) calls
``GET /api/v2/trains/departures?from=<code>&hide_departed=true`` with **no**
``to``. That resolves to ``DepartureService.get_departures(..., to_station=None)``,
which must return every upcoming train leaving the origin across all lines,
with no arrival timing (there is no destination to arrive at). These tests
lock in that contract so the frontend can rely on it.

Queries are scoped to ``data_sources=["AMTRAK"]`` (plus ``skip_individual_refresh``
/ ``skip_gtfs_merge``) purely for hermeticity — it keeps the NJT external client
and the GTFS static merge out of the test. The endpoint itself passes all
sources; the ``to_station=None`` shaping under test is source-independent.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.amtrak import create_amtrak_journey, create_amtrak_journey_stop
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _make_upcoming_amtrak(
    *,
    train_id: str,
    destination_name: str,
    destination_code: str,
    minutes_out: int,
    line_code: str,
    line_name: str,
    origin: str = "NY",
    has_departed_station: bool = False,
):
    """Build an Amtrak journey with an origin stop + one downstream stop."""
    depart_at = now_et() + timedelta(minutes=minutes_out)
    journey = create_amtrak_journey(
        train_id=train_id,
        origin=origin,
        destination=destination_name,
        scheduled_departure=depart_at,
        line_code=line_code,
        line_name=line_name,
    )
    journey.terminal_station_code = destination_code
    origin_stop = create_amtrak_journey_stop(
        station_code=origin,
        station_name="New York Penn Station",
        scheduled_departure=depart_at,
        stop_sequence=0,
        track="10",
        has_departed_station=has_departed_station,
        actual_departure=depart_at if has_departed_station else None,
    )
    dest_stop = create_amtrak_journey_stop(
        station_code=destination_code,
        station_name=destination_name,
        scheduled_arrival=depart_at + timedelta(minutes=60),
        stop_sequence=1,
    )
    journey.stops = [origin_stop, dest_stop]
    return journey


@pytest.mark.asyncio
class TestStationDepartures:
    """DepartureService.get_departures with to_station=None (single-station board)."""

    async def _query(self, service: DepartureService, db: AsyncSession):
        return await service.get_departures(
            db,
            from_station="NY",
            to_station=None,
            hide_departed=True,
            data_sources=["AMTRAK"],
            skip_individual_refresh=True,
            skip_gtfs_merge=True,
        )

    async def test_returns_all_upcoming_lines_without_arrival(
        self, db_session: AsyncSession
    ):
        """Every upcoming train from the origin is returned, sorted soonest-first,
        each with no arrival timing but a resolved destination name."""
        service = DepartureService()
        db_session.add_all(
            [
                _make_upcoming_amtrak(
                    train_id="A200",
                    destination_name="Albany-Rensselaer",
                    destination_code="ALB",
                    minutes_out=45,
                    line_code="EMP",
                    line_name="Empire Service",
                ),
                _make_upcoming_amtrak(
                    train_id="A100",
                    destination_name="Trenton",
                    destination_code="TR",
                    minutes_out=20,
                    line_code="NEC",
                    line_name="Northeast Regional",
                ),
            ]
        )
        await db_session.commit()

        response = await self._query(service, db_session)

        # Both upcoming trains, ordered by scheduled departure (soonest first).
        assert [d.train_id for d in response.departures] == ["A100", "A200"]
        # A single-station board has no destination, so no arrival timing.
        assert all(d.arrival is None for d in response.departures)
        # Destinations still tell the rider where each train is headed.
        assert {d.destination for d in response.departures} == {
            "Trenton",
            "Albany-Rensselaer",
        }
        # Metadata reflects the from-only query.
        assert response.metadata["from_station"]["code"] == "NY"
        assert response.metadata["to_station"] is None
        assert response.metadata["count"] == 2

    async def test_hide_departed_excludes_already_departed(
        self, db_session: AsyncSession
    ):
        """hide_departed=true drops trains that already left the origin."""
        service = DepartureService()
        departed = _make_upcoming_amtrak(
            train_id="GONE",
            destination_name="Trenton",
            destination_code="TR",
            minutes_out=-30,
            line_code="NEC",
            line_name="Northeast Regional",
            has_departed_station=True,
        )
        upcoming = _make_upcoming_amtrak(
            train_id="SOON",
            destination_name="Trenton",
            destination_code="TR",
            minutes_out=15,
            line_code="NEC",
            line_name="Northeast Regional",
        )
        db_session.add_all([departed, upcoming])
        await db_session.commit()

        response = await self._query(service, db_session)

        assert [d.train_id for d in response.departures] == ["SOON"]

    async def test_empty_when_no_upcoming_trains(self, db_session: AsyncSession):
        """A station with only already-departed trains yields an empty board."""
        service = DepartureService()
        departed = _make_upcoming_amtrak(
            train_id="GONE",
            destination_name="Trenton",
            destination_code="TR",
            minutes_out=-40,
            line_code="NEC",
            line_name="Northeast Regional",
            has_departed_station=True,
        )
        db_session.add(departed)
        await db_session.commit()

        response = await self._query(service, db_session)

        assert response.departures == []
        assert response.metadata["to_station"] is None
