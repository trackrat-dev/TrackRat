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

Uses ``skip_gtfs_merge=True`` to keep the test hermetic (no GTFS static data in
the test DB); matched-stop labeling runs on the real-time list regardless.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.config.stations import expand_station_codes
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


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
