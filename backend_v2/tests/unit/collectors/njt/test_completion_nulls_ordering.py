"""
Unit tests for NULL stop_sequence handling in _attempt_completion_on_expiry
(issue #1506).

Postgres sorts NULLs FIRST under ORDER BY ... DESC, and NJT discovery /
schedule generation create placeholder stops with stop_sequence = NULL. The
completion-on-expiry backstop picked its "terminal" and "penultimate" stops
positionally with ORDER BY stop_sequence DESC LIMIT 2, so on a journey
carrying a placeholder row the picks were arbitrary: a valid completion was
suppressed (train finalized as expired instead of completed) or, worse,
journey.actual_arrival could be written from a non-terminal stop.

These tests run against real PostgreSQL — SQLite (used by some collector
unit tests) orders NULLs LAST on DESC, the opposite semantics, so this bug
class is structurally invisible there.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture
def journey_collector():
    return JourneyCollector(AsyncMock(spec=NJTransitClient))


def _journey() -> TrainJourney:
    return TrainJourney(
        train_id="3922",
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="PJ",
        terminal_station_code="NY",
        data_source="NJT",
        scheduled_departure=now_et() - timedelta(hours=2),
        has_complete_journey=True,
        is_completed=False,
        is_expired=False,
        observation_type="OBSERVED",
    )


class TestCompletionNullsOrdering:
    @pytest.mark.asyncio
    async def test_completes_despite_stray_null_sequence_placeholder(
        self, db_session: AsyncSession, journey_collector
    ):
        """A journey whose real penultimate stop departed (api_explicit) and
        whose terminal arrival is due must complete even when a stray
        NULL-sequence placeholder row exists. Before the fix, Postgres
        returned the placeholder FIRST on DESC, so the gate evaluated the
        wrong stops and the completion was suppressed.
        """
        base = now_et() - timedelta(hours=2)

        journey = _journey()
        db_session.add(journey)
        await db_session.flush()

        db_session.add_all(
            [
                JourneyStop(
                    journey=journey,
                    station_code="PJ",
                    station_name="Princeton Junction",
                    stop_sequence=0,
                    scheduled_departure=base,
                    actual_departure=base,
                    has_departed_station=True,
                    departure_source="api_explicit",
                ),
                JourneyStop(
                    journey=journey,
                    station_code="NP",
                    station_name="Newark Penn Station",
                    stop_sequence=5,
                    scheduled_departure=base + timedelta(minutes=45),
                    actual_departure=base + timedelta(minutes=45),
                    has_departed_station=True,
                    departure_source="api_explicit",
                ),
                JourneyStop(
                    journey=journey,
                    station_code="NY",
                    station_name="New York Penn Station",
                    stop_sequence=10,
                    scheduled_arrival=base + timedelta(minutes=60),
                    has_departed_station=False,
                ),
                # Stray placeholder from discovery — NULL sequence.
                JourneyStop(
                    journey=journey,
                    station_code="SE",
                    station_name="Secaucus Upper Lvl",
                    stop_sequence=None,
                    scheduled_departure=base + timedelta(minutes=50),
                    has_departed_station=False,
                ),
            ]
        )
        await db_session.flush()

        await journey_collector._attempt_completion_on_expiry(db_session, journey)

        assert journey.is_completed is True, (
            "Valid completion must not be suppressed by a NULL-sequence "
            "placeholder being picked as 'terminal' (issue #1506)"
        )
        assert (
            journey.actual_arrival is not None
        ), "Terminal arrival must be recorded from the REAL terminal stop"

    @pytest.mark.asyncio
    async def test_no_positional_completion_when_top_stops_unsequenced(
        self, db_session: AsyncSession, journey_collector
    ):
        """When the top-2 picks still include unsequenced placeholder rows
        (partially-collected journey), positional detection can't be trusted
        — the backstop must decline rather than complete against arbitrary
        stops (same posture as utils/train.terminal_stop_index).
        """
        base = now_et() - timedelta(hours=2)

        journey = _journey()
        db_session.add(journey)
        await db_session.flush()

        db_session.add_all(
            [
                JourneyStop(
                    journey=journey,
                    station_code="PJ",
                    station_name="Princeton Junction",
                    stop_sequence=0,
                    scheduled_departure=base,
                    actual_departure=base,
                    has_departed_station=True,
                    departure_source="api_explicit",
                ),
                # Placeholder with NULL sequence — journey never fully
                # collected. With nulls_last it sorts below the sequenced
                # stop, so it lands in the top-2 picks.
                JourneyStop(
                    journey=journey,
                    station_code="SE",
                    station_name="Secaucus Upper Lvl",
                    stop_sequence=None,
                    scheduled_arrival=base + timedelta(minutes=20),
                    has_departed_station=False,
                ),
            ]
        )
        await db_session.flush()

        await journey_collector._attempt_completion_on_expiry(db_session, journey)

        assert journey.is_completed is False, (
            "A partially-collected journey (unsequenced placeholder in the "
            "positional picks) must not be force-completed"
        )
        assert journey.actual_arrival is None
