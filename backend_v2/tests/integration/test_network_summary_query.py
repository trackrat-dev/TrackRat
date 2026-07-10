"""
Integration tests for SummaryService._query_line_stats_sql (network scope).

Regression coverage for issue #1365: the last-stop-per-journey subquery must
filter by the recency cutoff *before* DISTINCT ON runs, not after, and must
never let a NULL stop_sequence outrank a journey's real terminal stop.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.summary import SummaryService
from trackrat.utils.time import now_et


def _make_journey(
    *,
    train_id: str,
    last_updated_at,
    line_code: str = "NE",
    data_source: str = "NJT",
) -> TrainJourney:
    """Build a minimal journey for network-summary query tests."""
    scheduled_departure = last_updated_at
    return TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        data_source=data_source,
        line_code=line_code,
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=scheduled_departure,
        first_seen_at=last_updated_at,
        last_updated_at=last_updated_at,
        update_count=1,
    )


@pytest.mark.asyncio
class TestNetworkSummaryQuery:
    """SummaryService._query_line_stats_sql behavioral coverage."""

    async def test_excludes_journeys_outside_cutoff_window(
        self, db_session: AsyncSession
    ):
        """A journey last updated outside the window must not count toward
        network stats, even though the last-stop subquery scans journey_stops
        without an outer filter applied first."""
        current_time = now_et()
        cutoff_time = current_time - timedelta(minutes=120)

        recent = _make_journey(train_id="100", last_updated_at=current_time - timedelta(minutes=10))
        recent.stops = [
            JourneyStop(
                station_code="TR",
                station_name="Trenton",
                stop_sequence=1,
                scheduled_arrival=current_time - timedelta(minutes=5),
                actual_arrival=current_time - timedelta(minutes=5),
                arrival_source="api_observed",
            )
        ]

        stale = _make_journey(train_id="200", last_updated_at=current_time - timedelta(hours=5))
        stale.stops = [
            JourneyStop(
                station_code="TR",
                station_name="Trenton",
                stop_sequence=1,
                scheduled_arrival=current_time - timedelta(hours=5),
                actual_arrival=current_time - timedelta(hours=5),
                arrival_source="api_observed",
            )
        ]

        db_session.add_all([recent, stale])
        await db_session.commit()

        service = SummaryService()
        line_stats = await service._query_line_stats_sql(db_session, cutoff_time)

        total_trains = sum(stats.train_count for stats in line_stats.values())
        assert total_trains == 1

    async def test_last_stop_is_highest_stop_sequence_not_a_null_one(
        self, db_session: AsyncSession
    ):
        """A NULL stop_sequence row must never outrank a journey's real
        terminal stop when picking the "last stop" for delay calculation."""
        current_time = now_et()
        cutoff_time = current_time - timedelta(minutes=120)

        journey = _make_journey(train_id="300", last_updated_at=current_time - timedelta(minutes=10))
        scheduled_terminal_arrival = current_time - timedelta(minutes=5)
        journey.stops = [
            # Origin stop, no arrival data.
            JourneyStop(
                station_code="NY",
                station_name="New York Penn Station",
                stop_sequence=0,
                scheduled_departure=current_time - timedelta(minutes=30),
            ),
            # Real terminal stop: on time.
            JourneyStop(
                station_code="TR",
                station_name="Trenton",
                stop_sequence=1,
                scheduled_arrival=scheduled_terminal_arrival,
                actual_arrival=scheduled_terminal_arrival,
                arrival_source="api_observed",
            ),
            # Stray row with no sequence assigned yet and a huge fake delay -
            # must not be picked over the real terminal stop above.
            JourneyStop(
                station_code="XX",
                station_name="Unknown",
                stop_sequence=None,
                scheduled_arrival=scheduled_terminal_arrival,
                actual_arrival=scheduled_terminal_arrival + timedelta(hours=3),
                arrival_source="api_observed",
            ),
        ]
        db_session.add(journey)
        await db_session.commit()

        service = SummaryService()
        line_stats = await service._query_line_stats_sql(db_session, cutoff_time)

        assert len(line_stats) == 1
        stats = next(iter(line_stats.values()))
        assert stats.arrival_data_count == 1
        assert stats.on_time_count == 1
        assert stats.total_delay_minutes == 0.0
