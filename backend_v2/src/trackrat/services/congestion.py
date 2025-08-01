"""
Route congestion analysis service.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models import SegmentTransitTime
from trackrat.utils.time import now_et

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
        color: str,
        avg_transit_minutes: float,
        baseline_minutes: float,
        sample_count: int,
        last_updated: datetime,
    ):
        self.from_station = from_station
        self.to_station = to_station
        self.data_source = data_source
        self.congestion_factor = congestion_factor
        self.congestion_level = congestion_level
        self.color = color
        self.avg_transit_minutes = avg_transit_minutes
        self.baseline_minutes = baseline_minutes
        self.sample_count = sample_count
        self.last_updated = last_updated
        self.from_station_coords: dict[str, float] | None = None
        self.to_station_coords: dict[str, float] | None = None


class CongestionAnalyzer:
    """Analyzes route congestion based on recent segment performance."""

    async def get_network_congestion(
        self, db: AsyncSession, time_window_hours: int = 3
    ) -> list[SegmentCongestion]:
        """
        Get congestion data for all active segments.

        Args:
            db: Database session
            time_window_hours: How many hours to look back

        Returns:
            List of segment congestion data
        """
        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # Get all recent segment times
        stmt = (
            select(SegmentTransitTime)
            .where(SegmentTransitTime.departure_time > cutoff_time)
            .order_by(SegmentTransitTime.departure_time.desc())
        )

        result = await db.execute(stmt)
        recent_segments = list(result.scalars().all())

        # Group by segment and calculate congestion
        segment_groups: dict[tuple[str, str, str], list[SegmentTransitTime]] = {}
        for segment in recent_segments:
            # Skip segments with None values
            if not all(
                [
                    segment.from_station_code,
                    segment.to_station_code,
                    segment.data_source,
                ]
            ):
                continue

            # Type assertions after None check
            from_code = str(segment.from_station_code)
            to_code = str(segment.to_station_code)
            source = str(segment.data_source)

            key = (from_code, to_code, source)
            if key not in segment_groups:
                segment_groups[key] = []
            segment_groups[key].append(segment)

        congestion_data = []
        for (from_station, to_station, data_source), segments in segment_groups.items():
            if len(segments) < 2:
                continue

            # Get baseline (use scheduled time or median)
            scheduled_times = [
                s.scheduled_minutes for s in segments if s.scheduled_minutes
            ]
            if scheduled_times:
                baseline_minutes = sum(scheduled_times) / len(scheduled_times)
            else:
                # Use median of actual times as baseline
                actual_times = sorted(
                    [s.actual_minutes for s in segments if s.actual_minutes is not None]
                )
                if not actual_times:
                    continue
                baseline_minutes = float(actual_times[len(actual_times) // 2])

            # Calculate current congestion (using recent times)
            recent_times = [
                s.actual_minutes for s in segments[:5] if s.actual_minutes is not None
            ]
            if not recent_times:
                continue
            current_avg = sum(recent_times) / len(recent_times)
            congestion_factor = (
                current_avg / baseline_minutes if baseline_minutes > 0 else 1.0
            )

            # Determine congestion level and color
            if congestion_factor <= 1.1:
                level = "normal"
                color = "#00ff00"  # Green
            elif congestion_factor <= 1.25:
                level = "moderate"
                color = "#ffff00"  # Yellow
            elif congestion_factor <= 1.5:
                level = "heavy"
                color = "#ff8800"  # Orange
            else:
                level = "severe"
                color = "#ff0000"  # Red

            congestion_data.append(
                SegmentCongestion(
                    from_station=from_station,
                    to_station=to_station,
                    data_source=data_source,
                    congestion_factor=congestion_factor,
                    congestion_level=level,
                    color=color,
                    avg_transit_minutes=current_avg,
                    baseline_minutes=baseline_minutes,
                    sample_count=len(recent_times),
                    last_updated=segments[0].departure_time or now_et(),
                )
            )

        logger.info(
            "network_congestion_calculated",
            segment_count=len(congestion_data),
            time_window_hours=time_window_hours,
        )

        return congestion_data
