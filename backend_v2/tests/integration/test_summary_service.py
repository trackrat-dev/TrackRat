"""
Integration tests for SummaryService against a real database.

Covers _query_line_stats_sql, which the unit tests in
tests/unit/services/test_summary.py mock entirely (db.execute is stubbed),
so the actual SQL join/filter/window logic has no real-database coverage
elsewhere. Regression test for issue #1366: the `last_stops` subquery must
stay scoped to journeys inside the cutoff window rather than scanning all
of journey_stops.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.summary import SummaryService
from trackrat.utils.time import now_et


def _make_journey(**overrides) -> TrainJourney:
    defaults = {
        "train_id": "1234",
        "journey_date": now_et().date(),
        "data_source": "NJT",
        "line_code": "NE",
        "line_name": "Northeast Corridor",
        "destination": "Trenton",
        "origin_station_code": "NY",
        "terminal_station_code": "TR",
        "scheduled_departure": now_et(),
        "last_updated_at": now_et(),
        "has_complete_journey": True,
        "update_count": 1,
    }
    defaults.update(overrides)
    return TrainJourney(**defaults)


@pytest.mark.asyncio
class TestQueryLineStatsSqlIntegration:
    """Real-database coverage for the last-stop-per-journey aggregation."""

    async def test_excludes_journeys_outside_cutoff_window(
        self, db_session: AsyncSession
    ):
        """A journey last updated before the cutoff must not contribute to
        line stats, even though its stops are still in journey_stops."""
        now = now_et()
        cutoff = now - timedelta(minutes=120)

        in_window = _make_journey(
            train_id="1001", last_updated_at=now - timedelta(minutes=10)
        )
        in_window.stops = [
            JourneyStop(
                station_code="NY",
                station_name="New York",
                stop_sequence=0,
                scheduled_arrival=now - timedelta(minutes=90),
                actual_arrival=now - timedelta(minutes=90),
                has_departed_station=True,
            ),
            JourneyStop(
                station_code="TR",
                station_name="Trenton",
                stop_sequence=1,
                scheduled_arrival=now - timedelta(minutes=30),
                actual_arrival=now - timedelta(minutes=25),
                arrival_source="api_observed",
                has_departed_station=True,
            ),
        ]

        stale = _make_journey(train_id="2002", last_updated_at=now - timedelta(hours=6))
        stale.stops = [
            JourneyStop(
                station_code="NY",
                station_name="New York",
                stop_sequence=0,
                scheduled_arrival=now - timedelta(hours=6),
                actual_arrival=now - timedelta(hours=6),
                arrival_source="api_observed",
                has_departed_station=True,
            )
        ]

        db_session.add_all([in_window, stale])
        await db_session.commit()

        service = SummaryService()
        line_stats = await service._query_line_stats_sql(
            db_session, cutoff, data_source=None
        )

        assert set(line_stats) == {"NJT:Northeast Corridor"}
        stats = line_stats["NJT:Northeast Corridor"]
        assert stats.train_count == 1
        assert stats.arrival_data_count == 1
        # 5 minute delay (scheduled -30min, actual -25min) is within the
        # 5-minute on-time threshold.
        assert stats.on_time_count == 1

    async def test_picks_highest_stop_sequence_as_last_stop(
        self, db_session: AsyncSession
    ):
        """The DISTINCT ON must resolve to the highest stop_sequence, not
        an arbitrary stop, for journeys with more than two stops."""
        now = now_et()
        cutoff = now - timedelta(minutes=120)

        journey = _make_journey(train_id="3003")
        journey.stops = [
            JourneyStop(
                station_code="NY",
                station_name="New York",
                stop_sequence=0,
                scheduled_arrival=now - timedelta(minutes=90),
                actual_arrival=now - timedelta(minutes=90),
                has_departed_station=True,
            ),
            JourneyStop(
                station_code="NP",
                station_name="Newark Penn",
                stop_sequence=1,
                # Deliberately "very late" here; must NOT be used as the
                # journey's final delay figure.
                scheduled_arrival=now - timedelta(minutes=70),
                actual_arrival=now - timedelta(minutes=10),
                arrival_source="api_observed",
                has_departed_station=True,
            ),
            JourneyStop(
                station_code="TR",
                station_name="Trenton",
                stop_sequence=2,
                scheduled_arrival=now - timedelta(minutes=30),
                actual_arrival=now - timedelta(minutes=29),
                arrival_source="api_observed",
                has_departed_station=True,
            ),
        ]
        db_session.add(journey)
        await db_session.commit()

        service = SummaryService()
        line_stats = await service._query_line_stats_sql(
            db_session, cutoff, data_source=None
        )

        stats = line_stats["NJT:Northeast Corridor"]
        # 1 minute delay at the true final stop (Trenton), not the 60
        # minute delay recorded mid-journey at Newark Penn.
        assert stats.total_delay_minutes == pytest.approx(1.0, abs=0.1)
        assert stats.on_time_count == 1
