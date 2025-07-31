"""
Service for analyzing recent train performance on similar routes.
"""

from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.models import SegmentTransitTime, TrainJourney

logger = get_logger(__name__)


class RecentTrainAnalyzer:
    """Analyzes recent trains on the same route for predictions."""

    async def get_recent_similar_trains(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
        hours_back: int = 6,
        limit: int = 10,
    ) -> list[TrainJourney]:
        """
        Get recent trains that traveled the same route.

        Args:
            db: Database session
            from_station: Starting station code
            to_station: Destination station code
            data_source: NJT or AMTRAK
            hours_back: How many hours to look back
            limit: Maximum number of trains to return

        Returns:
            List of recent journeys on the same route
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # Find journeys that:
        # 1. Have the same data source
        # 2. Are recent (within hours_back)
        # 3. Have actual departure times (completed or in progress)
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == data_source,
                    TrainJourney.actual_departure.isnot(None),
                    TrainJourney.last_updated_at > cutoff_time,
                )
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(TrainJourney.actual_departure.desc())
            .distinct()
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys containing both stations in correct order
        similar_trains = []
        for journey in all_journeys:
            # Check if journey contains our route
            from_idx = to_idx = None
            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_idx = stop.stop_sequence
                elif stop.station_code == to_station:
                    to_idx = stop.stop_sequence

            if from_idx is not None and to_idx is not None and from_idx < to_idx:
                similar_trains.append(journey)
                if len(similar_trains) >= limit:
                    break

        logger.debug(
            "found_similar_trains",
            from_station=from_station,
            to_station=to_station,
            data_source=data_source,
            count=len(similar_trains),
        )

        return similar_trains

    async def get_recent_segment_performance(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
        hours_back: int = 4,
    ) -> dict[str, float] | None:
        """
        Get recent performance metrics for a specific segment.

        Args:
            db: Database session
            from_station: Starting station code
            to_station: Ending station code
            data_source: NJT or AMTRAK
            hours_back: How many hours to look back

        Returns:
            Performance metrics or None if no data
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        stmt = (
            select(SegmentTransitTime)
            .where(
                and_(
                    SegmentTransitTime.from_station_code == from_station,
                    SegmentTransitTime.to_station_code == to_station,
                    SegmentTransitTime.data_source == data_source,
                    SegmentTransitTime.departure_time > cutoff_time,
                )
            )
            .order_by(SegmentTransitTime.departure_time.desc())
            .limit(20)
        )

        result = await db.execute(stmt)
        recent_segments = list(result.scalars().all())

        if not recent_segments:
            return None

        # Filter out None values for proper type checking
        transit_times = [
            s.actual_minutes for s in recent_segments if s.actual_minutes is not None
        ]
        delays = [
            s.delay_minutes for s in recent_segments if s.delay_minutes is not None
        ]

        if not transit_times or not delays:
            return None

        latest_time = float(transit_times[0]) if transit_times else 0.0

        return {
            "avg_transit_minutes": sum(transit_times) / len(transit_times),
            "avg_delay_minutes": sum(delays) / len(delays),
            "sample_count": len(recent_segments),
            "latest_transit_minutes": latest_time,
        }

    def calculate_segment_time(
        self, journey: TrainJourney, from_station: str, to_station: str
    ) -> int | None:
        """
        Calculate time taken between two stations for a journey.

        Args:
            journey: The journey to analyze
            from_station: Starting station code
            to_station: Ending station code

        Returns:
            Minutes taken or None if data not available
        """
        from_stop = None
        to_stop = None

        for stop in journey.stops:
            if stop.station_code == from_station and stop.actual_departure:
                from_stop = stop
            elif stop.station_code == to_station and stop.actual_arrival:
                to_stop = stop

        if (
            not from_stop
            or not to_stop
            or not from_stop.actual_departure
            or not to_stop.actual_arrival
        ):
            return None

        time_delta = to_stop.actual_arrival - from_stop.actual_departure
        return int(time_delta.total_seconds() / 60)
