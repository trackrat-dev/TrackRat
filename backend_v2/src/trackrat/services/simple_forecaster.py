"""
Simple arrival time forecaster using recent trains.

This service predicts arrival times by looking at how long recent trains
took to travel each segment of the journey.
"""

import statistics
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models.database import SegmentTransitTime, TrainJourney
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)


def _get_station_code(stop) -> str:
    """Get station code from either JourneyStop or StopDetails object."""
    if hasattr(stop, 'station_code'):
        return stop.station_code
    elif hasattr(stop, 'station') and hasattr(stop.station, 'code'):
        return stop.station.code
    else:
        raise AttributeError(f"Cannot get station code from {type(stop)} object")


class SimpleArrivalForecaster:
    """
    Ultra-simple arrival forecaster using recent trains on the same segments.
    
    Uses only trains from the last hour to capture current conditions.
    """
    
    LOOKBACK_HOURS = 1  # How far back to look for recent trains
    MIN_SAMPLES = 3     # Minimum trains needed for a prediction
    MAX_SEGMENT_MINUTES = 60  # Maximum believable time for a single segment
    
    async def add_predictions_to_stops(
        self,
        db: AsyncSession,
        journey: TrainJourney,
        stops: list
    ) -> None:
        """
        Add predicted_arrival times to stop objects in-place.
        
        Args:
            db: Database session
            journey: The train journey
            stops: List of stop objects (modified in-place)
        """
        logger.info("🔮 Starting arrival prediction", 
                   train_id=journey.train_id, 
                   journey_date=journey.journey_date,
                   num_stops=len(stops))
        
        if not stops:
            logger.info("🔮 No stops provided, skipping predictions")
            return
            
        # Sort stops by sequence to ensure correct order
        stops.sort(key=lambda s: s.stop_sequence)
        
        # Find current position (last departed stop)
        current_index = self._find_current_position(stops)
        
        logger.info("🚂 Train position analysis",
                   train_id=journey.train_id,
                   current_index=current_index,
                   total_stops=len(stops),
                   current_station=_get_station_code(stops[current_index]) if current_index < len(stops) else "UNKNOWN",
                   stops_remaining=len(stops) - current_index - 1)
        
        if current_index >= len(stops) - 1:
            # Already at or past destination
            logger.info("🏁 Train at or past destination, no predictions needed",
                       train_id=journey.train_id,
                       current_index=current_index,
                       total_stops=len(stops))
            return
        
        # Start accumulating time from the train's current position
        current_stop = stops[current_index]
        
        # For the origin station, use scheduled departure time as the starting point
        if current_index == 0:
            # Train is at origin - use scheduled departure as base time
            if hasattr(current_stop, 'scheduled_departure') and current_stop.scheduled_departure:
                predicted_time = ensure_timezone_aware(current_stop.scheduled_departure)
                logger.info("🚂 Using scheduled departure from origin",
                           station=_get_station_code(current_stop),
                           scheduled_departure=predicted_time.isoformat())
            else:
                # Fallback to current time if no schedule
                predicted_time = now_et()
                logger.warning("🚂 No scheduled departure, using current time",
                              station=_get_station_code(current_stop))
        else:
            # Train has departed from origin - start from current time
            predicted_time = now_et()
            logger.info("🚂 Train in progress, using current time",
                       current_station=_get_station_code(current_stop))
        
        # Process each remaining segment
        for i in range(current_index, len(stops) - 1):
            from_stop = stops[i]
            to_stop = stops[i + 1]
            
            # Get recent times for this segment
            segment_times = await self._get_recent_segment_times(
                db,
                _get_station_code(from_stop),
                _get_station_code(to_stop),
                journey.data_source
            )
            
            # Calculate transit time for this segment
            transit_minutes = self._calculate_segment_time(
                segment_times,
                from_stop,
                to_stop
            )
            
            # Check for unreasonable segment time
            if transit_minutes > self.MAX_SEGMENT_MINUTES:
                logger.warning(
                    "segment_time_too_long",
                    from_station=_get_station_code(from_stop),
                    to_station=_get_station_code(to_stop),
                    minutes=transit_minutes
                )
                # Fall back to using updated arrival if available
                if to_stop.updated_arrival:
                    to_stop.predicted_arrival = ensure_timezone_aware(to_stop.updated_arrival)
                    to_stop.predicted_arrival_samples = 0  # No samples, using fallback
                    predicted_time = to_stop.predicted_arrival
                else:
                    # Skip prediction for this stop
                    to_stop.predicted_arrival = None
                    to_stop.predicted_arrival_samples = 0
                continue
            
            # Add transit time to get arrival at next stop
            predicted_time = predicted_time + timedelta(minutes=transit_minutes)
            
            # Store prediction and sample count
            # Skip prediction for first stop (origin) since it's not meaningful
            if i + 1 > 0:  # to_stop is not the origin station
                to_stop.predicted_arrival = predicted_time
                to_stop.predicted_arrival_samples = len(segment_times)
                
                logger.info("✅ Prediction stored",
                           station=_get_station_code(to_stop),
                           predicted_arrival=predicted_time.isoformat(),
                           samples=len(segment_times),
                           transit_minutes=round(transit_minutes, 1),
                           from_station=_get_station_code(from_stop))
            else:
                logger.info("🏁 Skipping prediction for origin station",
                           station=_get_station_code(to_stop))
    
    def _find_current_position(self, stops: list) -> int:
        """
        Find the index of the last departed stop.
        
        Returns:
            Index of the current position (last departed stop)
        """
        current_index = 0
        
        for i, stop in enumerate(stops):
            if stop.has_departed_station:
                current_index = i
            elif hasattr(stop, 'actual_departure') and stop.actual_departure:
                # Check if actual departure is in the past
                if ensure_timezone_aware(stop.actual_departure) <= now_et():
                    current_index = i
        
        return current_index
    
    async def _get_recent_segment_times(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str
    ) -> list[float]:
        """
        Get actual transit times from recent trains on this segment.
        
        Args:
            db: Database session
            from_station: Origin station code
            to_station: Destination station code
            data_source: NJT or AMTRAK
            
        Returns:
            List of transit times in minutes
        """
        cutoff_time = now_et() - timedelta(hours=self.LOOKBACK_HOURS)
        
        logger.info("🕐 Querying segment times", 
                   from_station=from_station,
                   to_station=to_station, 
                   data_source=data_source,
                   lookback_hours=self.LOOKBACK_HOURS,
                   cutoff_time=cutoff_time.isoformat())
        
        # First check if there are ANY segment times for this route (ever)
        total_count_stmt = (
            select(SegmentTransitTime)
            .where(
                and_(
                    SegmentTransitTime.from_station_code == from_station,
                    SegmentTransitTime.to_station_code == to_station,
                    SegmentTransitTime.data_source == data_source
                )
            )
        )
        total_result = await db.execute(total_count_stmt)
        total_segments = total_result.fetchall()
        
        logger.info("📊 Segment analysis", 
                   from_station=from_station,
                   to_station=to_station,
                   total_segments_all_time=len(total_segments))
        
        if len(total_segments) > 0:
            # Show some example times for debugging
            latest_segments = sorted(total_segments, key=lambda x: x[0].departure_time, reverse=True)[:3]
            logger.info("🔍 Latest segment examples",
                       examples=[(s[0].departure_time.isoformat(), s[0].actual_minutes) 
                                for s in latest_segments])
        
        stmt = (
            select(SegmentTransitTime.actual_minutes)
            .where(
                and_(
                    SegmentTransitTime.from_station_code == from_station,
                    SegmentTransitTime.to_station_code == to_station,
                    SegmentTransitTime.data_source == data_source,
                    SegmentTransitTime.departure_time >= cutoff_time,
                    # Sanity filters
                    SegmentTransitTime.actual_minutes > 0,
                    SegmentTransitTime.actual_minutes <= self.MAX_SEGMENT_MINUTES
                )
            )
            .order_by(SegmentTransitTime.departure_time.desc())
            .limit(20)  # Cap at 20 most recent
        )
        
        result = await db.execute(stmt)
        times = [row[0] for row in result.fetchall()]
        
        logger.info("⏱️ Recent segment query results",
                   from_station=from_station,
                   to_station=to_station,
                   recent_count=len(times),
                   times=times[:5] if times else [],  # Log first 5 for debugging
                   min_samples_required=self.MIN_SAMPLES,
                   will_predict=len(times) >= self.MIN_SAMPLES)
        
        # If no actual segment times exist, try to get scheduled times from recent journeys
        if len(times) == 0:
            logger.info("🕰️ No actual segment data, trying scheduled times from recent journeys")
            times = await self._get_recent_scheduled_segment_times(
                db, from_station, to_station, data_source
            )
        
        return times
    
    async def _get_recent_scheduled_segment_times(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str
    ) -> list[float]:
        """
        Get scheduled transit times from recent journeys as a fallback.
        
        Args:
            db: Database session
            from_station: Origin station code
            to_station: Destination station code
            data_source: NJT or AMTRAK
            
        Returns:
            List of scheduled transit times in minutes
        """
        cutoff_time = now_et() - timedelta(hours=self.LOOKBACK_HOURS)
        
        logger.info("📋 Querying scheduled segment times", 
                   from_station=from_station,
                   to_station=to_station,
                   data_source=data_source,
                   cutoff_time=cutoff_time.isoformat())
        
        # Query for recent journeys that have both stops in sequence
        from trackrat.models.database import TrainJourney, JourneyStop
        from sqlalchemy import text
        
        # Use raw SQL for this complex query
        stmt = text("""
            SELECT 
                EXTRACT(EPOCH FROM (js2.scheduled_arrival - js1.scheduled_departure)) / 60.0 as minutes
            FROM train_journeys tj
            JOIN journey_stops js1 ON tj.id = js1.journey_id AND js1.station_code = :from_station
            JOIN journey_stops js2 ON tj.id = js2.journey_id AND js2.station_code = :to_station
            WHERE tj.data_source = :data_source
            AND tj.last_updated_at >= :cutoff_time
            AND js1.stop_sequence < js2.stop_sequence
            AND js1.scheduled_departure IS NOT NULL
            AND js2.scheduled_arrival IS NOT NULL
            LIMIT 10
        """)
        
        result = await db.execute(stmt, {
            'from_station': from_station,
            'to_station': to_station, 
            'data_source': data_source,
            'cutoff_time': cutoff_time
        })
        scheduled_rows = result.fetchall()
        
        # Extract valid transit times
        times = []
        for row in scheduled_rows:
            minutes = float(row.minutes) if row.minutes else 0
            if 0 < minutes <= self.MAX_SEGMENT_MINUTES:
                times.append(minutes)
        
        logger.info("📋 Scheduled times fallback results",
                   from_station=from_station,
                   to_station=to_station,
                   scheduled_count=len(times),
                   times=times[:3] if times else [])  # Log first 3
        
        return times
    
    def _calculate_segment_time(
        self,
        segment_times: list[float],
        from_stop,
        to_stop
    ) -> float:
        """
        Calculate the expected transit time for a segment.
        
        Uses median of recent times if available, otherwise falls back to scheduled.
        
        Args:
            segment_times: Recent actual transit times
            from_stop: Origin stop object
            to_stop: Destination stop object
            
        Returns:
            Expected transit time in minutes
        """
        if len(segment_times) >= self.MIN_SAMPLES:
            # Use median for robustness against outliers
            median_time = statistics.median(segment_times)
            logger.info("🎯 Using median prediction",
                       from_station=_get_station_code(from_stop),
                       to_station=_get_station_code(to_stop),
                       samples=len(segment_times),
                       median_minutes=round(median_time, 1),
                       all_times=segment_times)
            return median_time
        
        logger.info("📉 Insufficient samples, using fallback",
                   from_station=_get_station_code(from_stop),
                   to_station=_get_station_code(to_stop),
                   sample_count=len(segment_times),
                   min_required=self.MIN_SAMPLES)
        
        # Fallback to scheduled times if available
        if (hasattr(from_stop, 'scheduled_departure') and 
            hasattr(to_stop, 'scheduled_arrival') and
            from_stop.scheduled_departure and 
            to_stop.scheduled_arrival):
            
            scheduled_delta = (
                ensure_timezone_aware(to_stop.scheduled_arrival) -
                ensure_timezone_aware(from_stop.scheduled_departure)
            )
            scheduled_minutes = scheduled_delta.total_seconds() / 60.0
            
            # Sanity check scheduled time
            if 0 < scheduled_minutes <= self.MAX_SEGMENT_MINUTES:
                logger.info("📅 Using scheduled time fallback",
                           from_station=_get_station_code(from_stop),
                           to_station=_get_station_code(to_stop),
                           scheduled_minutes=round(scheduled_minutes, 1))
                return scheduled_minutes
        
        # Last resort: use a conservative default
        # This should rarely happen in practice
        logger.warning("❌ No segment data available, using default",
                      from_station=_get_station_code(from_stop),
                      to_station=_get_station_code(to_stop),
                      default_minutes=15.0)
        return 15.0  # Conservative 15-minute default