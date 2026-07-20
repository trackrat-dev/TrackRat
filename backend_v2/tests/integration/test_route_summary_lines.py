"""
Integration tests for the line-scoped route operations summary
(SummaryService.get_route_summary with line_codes, issue #1567).

Lines that share terminal stations (NJT Main and Bergen County both run
Hoboken→Suffern) previously produced identical summaries for the same
from/to pair because the journey query was keyed only by station pair and
data source. The ``line_codes`` filter scopes the summary to one line's
journeys, using the same raw ``TrainJourney.line_code`` match semantics as
the /routes/history ``lines`` filter (clients send every stored case
variant, e.g. 'MA' and legacy 'Ma').
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.summary import SummaryService
from trackrat.utils.time import now_et


def _make_route_journey(
    *,
    train_id: str,
    line_code: str,
    line_name: str,
    departed_minutes_ago: int,
    origin: str = "NY",
    destination: str = "TR",
) -> TrainJourney:
    """Build an NJT journey with origin + destination stops that departed
    the origin within the summary's 120-minute window."""
    departure = now_et() - timedelta(minutes=departed_minutes_ago)
    arrival = departure + timedelta(minutes=55)
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        data_source="NJT",
        line_code=line_code,
        line_name=line_name,
        line_color="#00A94F",
        destination="Trenton",
        origin_station_code=origin,
        terminal_station_code=destination,
        scheduled_departure=departure,
        first_seen_at=departure - timedelta(hours=1),
        last_updated_at=now_et() - timedelta(minutes=5),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code=origin,
            station_name="New York Penn Station",
            scheduled_departure=departure,
            actual_departure=departure,
            stop_sequence=0,
            has_departed_station=True,
        ),
        JourneyStop(
            station_code=destination,
            station_name="Trenton",
            scheduled_arrival=arrival,
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


async def _seed_shared_terminal_lines(db_session: AsyncSession) -> None:
    """Two Main Line trains (one legacy mixed-case row) and one Bergen train
    on the same station pair — the shared-terminal shape from issue #1567."""
    db_session.add_all(
        [
            _make_route_journey(
                train_id="MAIN_1",
                line_code="MA",
                line_name="Main Line",
                departed_minutes_ago=20,
            ),
            # Legacy mixed-case row as produced by parse_njt_line_code truncation
            _make_route_journey(
                train_id="MAIN_2",
                line_code="Ma",
                line_name="Main Line",
                departed_minutes_ago=40,
            ),
            _make_route_journey(
                train_id="BERGEN_1",
                line_code="BE",
                line_name="Bergen County Line",
                departed_minutes_ago=30,
            ),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
class TestRouteSummaryLineFilter:
    """SummaryService.get_route_summary line_codes behavioral coverage."""

    async def test_line_codes_scope_the_summary(self, db_session: AsyncSession):
        """Each line's summary counts only its own trains; unfiltered stays combined."""
        await _seed_shared_terminal_lines(db_session)

        main = await SummaryService().get_route_summary(
            db_session, "NY", "TR", "NJT", line_codes=["MA", "Ma"]
        )
        bergen = await SummaryService().get_route_summary(
            db_session, "NY", "TR", "NJT", line_codes=["BE", "Be"]
        )
        combined = await SummaryService().get_route_summary(
            db_session, "NY", "TR", "NJT"
        )

        assert combined.metrics is not None and combined.metrics.train_count == 3, (
            "Unfiltered summary must keep counting all trains on the station "
            f"pair; got metrics={combined.metrics}"
        )
        assert main.metrics is not None and main.metrics.train_count == 2, (
            "line_codes=['MA','Ma'] must count both Main variants and exclude "
            f"Bergen; got metrics={main.metrics}"
        )
        assert bergen.metrics is not None and bergen.metrics.train_count == 1, (
            "line_codes=['BE','Be'] must count only the Bergen train; got "
            f"metrics={bergen.metrics}"
        )

    async def test_disjoint_line_codes_yield_empty_summary(
        self, db_session: AsyncSession
    ):
        """A line with no trains in the window reads as no service, not as the
        other line's data."""
        await _seed_shared_terminal_lines(db_session)

        none_match = await SummaryService().get_route_summary(
            db_session, "NY", "TR", "NJT", line_codes=["NE"]
        )

        assert none_match.metrics is None, (
            "A line filter matching no journeys must not inherit the station "
            f"pair's combined data; got metrics={none_match.metrics}"
        )
        assert "No trains" in none_match.body

    async def test_cache_key_includes_line_codes(self, db_session: AsyncSession):
        """Different line scopes on the same station pair must not collide in
        the service's in-process cache — the second call must not be served
        the first call's cached summary."""
        await _seed_shared_terminal_lines(db_session)
        service = SummaryService()

        main = await service.get_route_summary(
            db_session, "NY", "TR", "NJT", line_codes=["MA", "Ma"]
        )
        bergen = await service.get_route_summary(
            db_session, "NY", "TR", "NJT", line_codes=["BE", "Be"]
        )
        combined = await service.get_route_summary(db_session, "NY", "TR", "NJT")

        assert main.metrics is not None and main.metrics.train_count == 2
        assert bergen.metrics is not None and bergen.metrics.train_count == 1, (
            "Bergen summary was served the Main line's cached result — the "
            "in-process cache key must include line_codes"
        )
        assert combined.metrics is not None and combined.metrics.train_count == 3, (
            "Unfiltered summary was served a line-scoped cached result — the "
            "in-process cache key must include line_codes"
        )
