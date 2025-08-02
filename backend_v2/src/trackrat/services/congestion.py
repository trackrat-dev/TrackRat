"""
Route congestion analysis service - On-the-fly calculation from journey data.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.models.database import TrainJourney
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)


class SegmentCongestion:
    """Congestion data for a route segment."""

    def __init__(
        self,
        from_station: str,
        to_station: str,
        data_source: str,
        congestion_factor: float,
        congestion_level: str,
        avg_transit_minutes: float,
        baseline_minutes: float,
        sample_count: int,
        average_delay_minutes: float,
        cancellation_count: int = 0,
        cancellation_rate: float = 0.0,
    ):
        self.from_station = from_station
        self.to_station = to_station
        self.data_source = data_source
        self.congestion_factor = congestion_factor
        self.congestion_level = congestion_level
        self.avg_transit_minutes = avg_transit_minutes
        self.baseline_minutes = baseline_minutes
        self.sample_count = sample_count
        self.average_delay_minutes = average_delay_minutes
        self.cancellation_count = cancellation_count
        self.cancellation_rate = cancellation_rate


class CongestionAnalyzer:
    """Analyzes route congestion in real-time from journey data."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[list[SegmentCongestion], datetime]] = {}
        self._cache_ttl = 300  # 5 minutes cache

    async def get_network_congestion_with_trains(
        self, db: AsyncSession, time_window_hours: int = 3
    ) -> tuple[list[SegmentCongestion], list[TrainJourney]]:
        """
        Get congestion data and train journeys.

        Returns:
            Tuple of (segment congestion data, train journeys)
        """
        segments = await self.get_network_congestion(db, time_window_hours)

        # Get the journeys from the last query (we need to re-query to get them)
        cutoff_time = now_et() - timedelta(hours=time_window_hours)
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.last_updated_at >= cutoff_time,
                )
            )
            .options(
                selectinload(TrainJourney.stops), selectinload(TrainJourney.progress)
            )
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        return segments, journeys

    async def get_network_congestion(
        self, db: AsyncSession, time_window_hours: int = 3
    ) -> list[SegmentCongestion]:
        """
        Get congestion data calculated on-the-fly from journey data.

        Args:
            db: Database session
            time_window_hours: How many hours to look back

        Returns:
            List of segment congestion data
        """
        # Check cache first
        cache_key = f"congestion_{time_window_hours}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if (now_et() - timestamp).total_seconds() < self._cache_ttl:
                logger.debug(
                    "returning_cached_congestion_data",
                    cache_age_seconds=(now_et() - timestamp).total_seconds(),
                )
                return cached_data

        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # Query journeys in the time window (including cancelled ones for stats)
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.last_updated_at >= cutoff_time,
                    # Include all journeys to capture cancellations
                )
            )
            .options(
                selectinload(TrainJourney.stops), selectinload(TrainJourney.progress)
            )
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        logger.info(
            "queried_journeys_for_congestion",
            journey_count=len(journeys),
            time_window_hours=time_window_hours,
            cutoff_time=cutoff_time.isoformat(),
        )

        # Calculate segments from journey data (separate active and cancelled)
        segment_data, cancellation_data = self._calculate_segments_from_journeys(
            journeys, cutoff_time
        )

        # Analyze congestion for each segment
        congestion_results = self._analyze_segment_congestion(
            segment_data, cancellation_data
        )

        # Cache the results
        self._cache[cache_key] = (congestion_results, now_et())

        logger.info(
            "network_congestion_calculated_on_the_fly",
            segment_count=len(congestion_results),
            time_window_hours=time_window_hours,
            total_journeys=len(journeys),
            unique_segment_groups=len(segment_data),
        )

        return congestion_results

    def _calculate_segments_from_journeys(
        self, journeys: list[TrainJourney], cutoff_time: datetime
    ) -> tuple[
        dict[tuple[str, str, str], list[dict[str, Any]]],
        dict[tuple[str, str, str], int],
    ]:
        """Extract segment data from journeys and track cancellations."""
        segment_groups: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = (
            defaultdict(list)
        )
        cancellation_counts: defaultdict[tuple[str, str, str], int] = defaultdict(int)

        for journey in journeys:
            if not journey.stops:
                continue

            # Sort stops by sequence
            sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

            # Track cancellations for each potential segment
            if journey.is_cancelled:
                # For cancelled journeys, count them against all segments they would have traveled
                for i in range(len(sorted_stops) - 1):
                    from_stop = sorted_stops[i]
                    to_stop = sorted_stops[i + 1]

                    if (
                        from_stop.station_code
                        and to_stop.station_code
                        and journey.data_source
                    ):
                        key = (
                            from_stop.station_code,
                            to_stop.station_code,
                            journey.data_source,
                        )
                        cancellation_counts[key] += 1
                continue  # Skip cancelled journeys from active segment calculation

            # Calculate segments between consecutive stops for active journeys
            for i in range(len(sorted_stops) - 1):
                from_stop = sorted_stops[i]
                to_stop = sorted_stops[i + 1]

                # Skip if missing critical data
                if not all(
                    [
                        from_stop.station_code,
                        to_stop.station_code,
                        from_stop.actual_departure or from_stop.scheduled_departure,
                        to_stop.actual_arrival or to_stop.scheduled_arrival,
                    ]
                ):
                    continue

                # Use actual times when available, fall back to scheduled
                departure_time = (
                    from_stop.actual_departure or from_stop.scheduled_departure
                )
                arrival_time = to_stop.actual_arrival or to_stop.scheduled_arrival

                if not departure_time or not arrival_time:
                    continue
                # Ensure timezone awareness
                departure_time = ensure_timezone_aware(departure_time)
                arrival_time = ensure_timezone_aware(arrival_time)

                # Skip if outside time window
                if departure_time < cutoff_time:
                    continue

                # Calculate segment duration
                actual_minutes = (arrival_time - departure_time).total_seconds() / 60
                if actual_minutes <= 0:
                    continue  # Skip invalid segments

                # Calculate scheduled duration if available
                scheduled_minutes = None
                if from_stop.scheduled_departure and to_stop.scheduled_arrival:
                    sched_dep = ensure_timezone_aware(from_stop.scheduled_departure)
                    sched_arr = ensure_timezone_aware(to_stop.scheduled_arrival)
                    scheduled_minutes = (sched_arr - sched_dep).total_seconds() / 60

                assert from_stop.station_code
                assert to_stop.station_code
                assert journey.data_source

                # Group by segment key
                key = (
                    from_stop.station_code,
                    to_stop.station_code,
                    journey.data_source,
                )
                segment_groups[key].append(
                    {
                        "actual_minutes": actual_minutes,
                        "scheduled_minutes": scheduled_minutes,
                        "departure_time": departure_time,
                        "journey_id": journey.id,
                        "train_id": journey.train_id,
                    }
                )

        return segment_groups, dict(cancellation_counts)

    def _analyze_segment_congestion(
        self,
        segment_groups: dict[tuple[str, str, str], list[dict[str, Any]]],
        cancellation_counts: dict[tuple[str, str, str], int],
    ) -> list[SegmentCongestion]:
        """Analyze congestion for each segment."""
        congestion_data = []

        # Get all unique segment keys from both active and cancelled data
        all_segment_keys = set(segment_groups.keys()) | set(cancellation_counts.keys())

        for segment_key in all_segment_keys:
            from_station, to_station, data_source = segment_key
            segments = segment_groups.get(segment_key, [])
            cancellation_count = cancellation_counts.get(segment_key, 0)

            # Calculate total journeys (active + cancelled)
            total_journeys = len(segments) + cancellation_count

            # Skip if we don't have enough data
            if total_journeys < 2:
                continue

            # Calculate cancellation rate
            cancellation_rate = (
                (cancellation_count / total_journeys * 100)
                if total_journeys > 0
                else 0.0
            )

            # For segments with only cancellations, create a special entry
            if len(segments) == 0:
                congestion_data.append(
                    SegmentCongestion(
                        from_station=from_station,
                        to_station=to_station,
                        data_source=data_source,
                        congestion_factor=1.0,  # No congestion data available
                        congestion_level="normal",  # Default level
                        avg_transit_minutes=0.0,
                        baseline_minutes=0.0,
                        sample_count=0,
                        average_delay_minutes=0.0,
                        cancellation_count=cancellation_count,
                        cancellation_rate=cancellation_rate,
                    )
                )
                continue

            # Calculate baseline (scheduled average or median of actuals)
            scheduled_times = [
                s["scheduled_minutes"]
                for s in segments
                if s["scheduled_minutes"] is not None
            ]

            if scheduled_times:
                baseline_minutes = statistics.mean(scheduled_times)
            else:
                # Use median of actual times as baseline
                actual_times = [s["actual_minutes"] for s in segments]
                baseline_minutes = statistics.median(actual_times)

            # Calculate current average (recent 50 samples, sorted by time)
            recent_segments = sorted(
                segments, key=lambda x: x["departure_time"], reverse=True
            )[:50]
            current_avg = statistics.mean(
                [s["actual_minutes"] for s in recent_segments]
            )

            # Calculate congestion factor
            congestion_factor = (
                current_avg / baseline_minutes if baseline_minutes > 0 else 1.0
            )

            # Calculate average delay
            average_delay_minutes = current_avg - baseline_minutes

            # Determine congestion level (same thresholds as before)
            if congestion_factor <= 1.1:
                level = "normal"
            elif congestion_factor <= 1.25:
                level = "moderate"
            elif congestion_factor <= 1.5:
                level = "heavy"
            else:
                level = "severe"

            congestion_data.append(
                SegmentCongestion(
                    from_station=from_station,
                    to_station=to_station,
                    data_source=data_source,
                    congestion_factor=congestion_factor,
                    congestion_level=level,
                    avg_transit_minutes=current_avg,
                    baseline_minutes=baseline_minutes,
                    sample_count=len(recent_segments),
                    average_delay_minutes=average_delay_minutes,
                    cancellation_count=cancellation_count,
                    cancellation_rate=cancellation_rate,
                )
            )

        return congestion_data
