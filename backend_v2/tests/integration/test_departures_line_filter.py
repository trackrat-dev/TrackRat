"""
Integration tests for line-scoped upcoming departures
(DepartureService.get_departures with line_codes, issue #1567 / PR #1585 review).

The web line-detail timeline's upcoming feed uses /trains/departures in line
mode. Because two lines can share terminal stations (NJT Main and Bergen
County both run Hoboken->Suffern), the `line_codes` filter scopes the board to
one line. Critically, the filter is applied to the merged departures list
*before* the limit, so a shared-terminal sibling with several earlier
departures cannot consume the limit and hide this line's next train.

Uses `skip_gtfs_merge=True` to keep the test hermetic (no GTFS static data in
the test DB); the line filter runs on the real-time list regardless.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _make_upcoming_journey(
    *,
    train_id: str,
    line_code: str,
    line_name: str,
    departs_in_minutes: int,
    origin: str = "HB",
    destination: str = "SF",
) -> TrainJourney:
    """NJT journey with an upcoming origin departure and a downstream stop."""
    departure = now_et() + timedelta(minutes=departs_in_minutes)
    arrival = departure + timedelta(minutes=50)
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        data_source="NJT",
        line_code=line_code,
        line_name=line_name,
        line_color="#00A94F",
        destination="Suffern",
        origin_station_code=origin,
        terminal_station_code=destination,
        scheduled_departure=departure,
        first_seen_at=now_et() - timedelta(minutes=30),
        last_updated_at=now_et() - timedelta(minutes=1),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code=origin,
            station_name="Hoboken",
            scheduled_departure=departure,
            stop_sequence=0,
            has_departed_station=False,
        ),
        JourneyStop(
            station_code=destination,
            station_name="Suffern",
            scheduled_arrival=arrival,
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


async def _seed(db_session: AsyncSession) -> None:
    """Three Bergen trains departing before a single (later) Main train.

    This is the shared-terminal shape that exposes the limit-before-filter bug:
    with a small limit and no line filter, the three earlier Bergen trains fill
    the board and the Main train is never returned.
    """
    db_session.add_all(
        [
            _make_upcoming_journey(
                train_id="BERGEN_1",
                line_code="BE",
                line_name="Bergen County Line",
                departs_in_minutes=10,
            ),
            _make_upcoming_journey(
                train_id="BERGEN_2",
                line_code="BE",
                line_name="Bergen County Line",
                departs_in_minutes=20,
            ),
            _make_upcoming_journey(
                train_id="BERGEN_3",
                line_code="BE",
                line_name="Bergen County Line",
                departs_in_minutes=30,
            ),
            _make_upcoming_journey(
                train_id="MAIN_1",
                line_code="MA",
                line_name="Main Line",
                departs_in_minutes=40,
            ),
            # Legacy mixed-case Main row (parse_njt_line_code truncation),
            # departing latest of all.
            _make_upcoming_journey(
                train_id="MAIN_2",
                line_code="Ma",
                line_name="Main Line",
                departs_in_minutes=50,
            ),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
class TestDeparturesLineFilter:
    """DepartureService.get_departures line_codes behavioral coverage."""

    async def test_line_codes_scope_the_board(self, db_session: AsyncSession):
        await _seed(db_session)
        service = DepartureService()

        main = await service.get_departures(
            db_session,
            "HB",
            "SF",
            hide_departed=True,
            data_sources=["NJT"],
            skip_gtfs_merge=True,
            line_codes=["MA", "Ma"],
        )
        bergen = await service.get_departures(
            db_session,
            "HB",
            "SF",
            hide_departed=True,
            data_sources=["NJT"],
            skip_gtfs_merge=True,
            line_codes=["BE", "Be"],
        )

        assert {d.train_id for d in main.departures} == {"MAIN_1", "MAIN_2"}, (
            "line_codes=['MA','Ma'] must return both Main variants and exclude "
            f"Bergen; got {[d.train_id for d in main.departures]}"
        )
        assert {d.train_id for d in bergen.departures} == {
            "BERGEN_1",
            "BERGEN_2",
            "BERGEN_3",
        }, (
            "line_codes=['BE','Be'] must return only Bergen trains; got "
            f"{[d.train_id for d in bergen.departures]}"
        )

    async def test_line_filter_applied_before_limit(self, db_session: AsyncSession):
        """The reviewer's core concern (PR #1585): a shared-terminal sibling's
        earlier departures must not consume the limit and hide this line's next
        train. The filter runs before the limit, so a Main-scoped request with a
        limit of 2 still returns the (later) Main train even though three Bergen
        trains depart first."""
        await _seed(db_session)
        service = DepartureService()

        # Sanity check: without a line filter, limit=2 returns the two earliest
        # (both Bergen) — the Main train is crowded out. This is the bug the
        # line filter fixes.
        combined = await service.get_departures(
            db_session,
            "HB",
            "SF",
            limit=2,
            hide_departed=True,
            data_sources=["NJT"],
            skip_gtfs_merge=True,
        )
        assert [d.train_id for d in combined.departures] == ["BERGEN_1", "BERGEN_2"], (
            "Precondition: unfiltered limit=2 should return the two earliest "
            f"(Bergen) trains; got {[d.train_id for d in combined.departures]}"
        )

        # With the line filter, the Main train survives despite the small limit
        # because filtering happens before truncation.
        main = await service.get_departures(
            db_session,
            "HB",
            "SF",
            limit=2,
            hide_departed=True,
            data_sources=["NJT"],
            skip_gtfs_merge=True,
            line_codes=["MA", "Ma"],
        )
        assert [d.train_id for d in main.departures] == ["MAIN_1", "MAIN_2"], (
            "line_codes must be applied before the limit so the sibling line's "
            "earlier departures can't hide the Main train; got "
            f"{[d.train_id for d in main.departures]}"
        )

    async def test_omitting_line_codes_keeps_combined_board(
        self, db_session: AsyncSession
    ):
        await _seed(db_session)
        service = DepartureService()

        combined = await service.get_departures(
            db_session,
            "HB",
            "SF",
            hide_departed=True,
            data_sources=["NJT"],
            skip_gtfs_merge=True,
        )

        assert {d.train_id for d in combined.departures} == {
            "BERGEN_1",
            "BERGEN_2",
            "BERGEN_3",
            "MAIN_1",
            "MAIN_2",
        }, "Omitting line_codes must keep the combined board unchanged"
