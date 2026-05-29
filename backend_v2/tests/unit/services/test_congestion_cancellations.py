"""Real-database tests for cancellation handling in network congestion.

Reproduces #1246: NJT NEC (Trenton -> NY Penn) had many cancellations while the
congestion map stayed green. Cancelled trains have no real-time arrival/departure
times, so the optimized congestion query used to filter them out before counting,
leaving cancellation_rate at ~0 and the displayed level unaffected.

These tests require a PostgreSQL test database because the congestion calculation
is a raw SQL query inside get_network_congestion_optimized.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.utils.time import now_et


async def _add_njt_nec_journey(
    db: AsyncSession,
    train_id: str,
    from_station: str,
    to_station: str,
    scheduled_departure: datetime,
    scheduled_arrival: datetime,
    *,
    is_cancelled: bool,
    actual_departure: datetime | None = None,
    actual_arrival: datetime | None = None,
) -> None:
    """Create an NJT NEC journey with a single from->to stop pair.

    Running trains get actual times; cancelled trains get only scheduled times,
    mirroring real data — a cancelled train never produces real-time times.
    """
    journey = TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York Penn Station",
        origin_station_code=from_station,
        terminal_station_code=to_station,
        data_source="NJT",
        observation_type="SCHEDULED" if is_cancelled else "OBSERVED",
        scheduled_departure=scheduled_departure,
        is_cancelled=is_cancelled,
        has_complete_journey=not is_cancelled,
        stops_count=2,
    )
    db.add(journey)
    await db.flush()

    db.add(
        JourneyStop(
            journey_id=journey.id,
            station_code=from_station,
            station_name=from_station,
            stop_sequence=1,
            scheduled_departure=scheduled_departure,
            actual_departure=actual_departure,
        )
    )
    db.add(
        JourneyStop(
            journey_id=journey.id,
            station_code=to_station,
            station_name=to_station,
            stop_sequence=2,
            scheduled_arrival=scheduled_arrival,
            actual_arrival=actual_arrival,
        )
    )
    await db.flush()


@pytest.mark.asyncio
class TestCongestionCancellationsRealDB:
    """End-to-end verification that cancelled trains affect congestion."""

    async def test_cancellations_counted_and_elevate_level(
        self, db_session: AsyncSession
    ):
        """5 on-time running + 5 cancelled NEC trains on NY->SE: the segment
        must report a ~50% cancellation rate and a level worse than 'normal'
        even though every running train is on time. Reproduces #1246.
        """
        dep = now_et() - timedelta(minutes=30)
        arr = dep + timedelta(minutes=5)

        for i in range(5):
            await _add_njt_nec_journey(
                db_session,
                train_id=f"run_{i}",
                from_station="NY",
                to_station="SE",
                scheduled_departure=dep,
                scheduled_arrival=arr,
                is_cancelled=False,
                actual_departure=dep,  # on time
                actual_arrival=arr,
            )
        for i in range(5):
            await _add_njt_nec_journey(
                db_session,
                train_id=f"cancel_{i}",
                from_station="NY",
                to_station="SE",
                scheduled_departure=dep,
                scheduled_arrival=arr,
                is_cancelled=True,
            )
        await db_session.commit()

        analyzer = CongestionAnalyzer()
        segments = await analyzer.get_network_congestion_optimized(
            db_session, time_window_hours=3, data_source="NJT"
        )

        ny_se = next(
            (s for s in segments if (s.from_station, s.to_station) == ("NY", "SE")),
            None,
        )
        assert ny_se is not None, "NY->SE segment should be present in results"
        # Running trains feed the active sample; cancelled trains are counted
        # separately (the old query dropped them, leaving this at 0).
        assert ny_se.sample_count == 5
        assert ny_se.cancellation_count == 5
        assert ny_se.cancellation_rate == pytest.approx(50.0)
        # On-time running trains -> delay factor ~1.0; cancellations alone must
        # push the level above normal (1.0 + 50% * 0.015 = 1.75 -> severe).
        assert ny_se.congestion_factor == pytest.approx(1.0, abs=0.05)
        assert ny_se.congestion_level == "severe"

    async def test_no_cancellations_segment_stays_normal(
        self, db_session: AsyncSession
    ):
        """Control: on-time running trains with no cancellations stay 'normal'."""
        dep = now_et() - timedelta(minutes=30)
        arr = dep + timedelta(minutes=5)

        for i in range(5):
            await _add_njt_nec_journey(
                db_session,
                train_id=f"run_{i}",
                from_station="NY",
                to_station="SE",
                scheduled_departure=dep,
                scheduled_arrival=arr,
                is_cancelled=False,
                actual_departure=dep,
                actual_arrival=arr,
            )
        await db_session.commit()

        analyzer = CongestionAnalyzer()
        segments = await analyzer.get_network_congestion_optimized(
            db_session, time_window_hours=3, data_source="NJT"
        )

        ny_se = next(
            (s for s in segments if (s.from_station, s.to_station) == ("NY", "SE")),
            None,
        )
        assert ny_se is not None
        assert ny_se.cancellation_count == 0
        assert ny_se.cancellation_rate == pytest.approx(0.0)
        assert ny_se.congestion_level == "normal"
