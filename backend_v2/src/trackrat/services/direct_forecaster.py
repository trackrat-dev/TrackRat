"""
Direct arrival time forecaster without intermediate segment storage.

This service calculates segment times directly from recent journeys,
eliminating the need for the segment_transit_times table entirely.
It queries journey_stops directly to find how long recent trains took.
"""

import statistics
from datetime import timedelta, timezone
from typing import Any

from sqlalchemy import and_, select, or_, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)


def _get_station_code(stop: Any) -> str:
    """Get station code from either JourneyStop or StopDetails object."""
    if hasattr(stop, "station_code"):
        return str(stop.station_code)
    elif hasattr(stop, "station") and hasattr(stop.station, "code"):
        return str(stop.station.code)
    else:
        raise AttributeError(f"Cannot get station code from {type(stop)} object")


class DirectArrivalForecaster:
    """
    Direct calculation forecaster - no intermediate segment storage.
    
    Calculates segment transit times on-the-fly by querying recent journeys
    directly. This eliminates the complexity of segment generation and ensures
    we always use the freshest data available.
    
    Key benefits:
    - No waiting for segment generation
    - Always uses the freshest data
    - Can't have "missing segment" bugs
    - Simpler architecture overall
    """

    # Configuration constants - easy to tune
    LOOKBACK_HOURS = 1  # How far back to look for recent trains
    MIN_SAMPLES = 2  # Minimum trains needed for a prediction (2 is reasonable)
    MAX_SEGMENT_MINUTES = 60  # Maximum believable time for a single segment
    STALE_PREDICTION_MINUTES = 10  # How old a prediction can be before we discard it

    async def add_predictions_to_stops(
        self,
        db: AsyncSession,
        journey: TrainJourney,
        stops: list[Any],
        user_origin: str | None = None,
    ) -> None:
        """
        Add predicted_arrival times to stop objects in-place.

        Args:
            db: Database session
            journey: The train journey
            stops: List of stop objects (modified in-place)
            user_origin: User's boarding station code (if provided)
        """
        try:
            logger.info(
                "🔮 Starting direct arrival prediction",
                train_id=journey.train_id,
                journey_date=journey.journey_date,
                num_stops=len(stops),
                user_origin=user_origin,
                data_source=journey.data_source,
                line_code=journey.line_code,
            )

            if not stops:
                logger.debug("No stops to process, returning early")
                return

            # Sort stops by sequence
            try:
                stops.sort(key=lambda s: s.stop_sequence)
            except AttributeError as e:
                logger.error(f"Stop object missing stop_sequence attribute: {e}")
                return

            # Find starting point and initial time
            start_index, predicted_time = self._determine_starting_point(stops, user_origin)
            
            if start_index is None or predicted_time is None:
                logger.warning(
                    "Could not determine starting point for predictions",
                    train_id=journey.train_id,
                    user_origin=user_origin,
                )
                return

            predictions_made = 0
            segments_processed = 0
            
            # Process each segment from the starting point
            for i in range(start_index, len(stops) - 1):
                segments_processed += 1
                from_stop = stops[i]
                to_stop = stops[i + 1]
                
                try:
                    from_code = _get_station_code(from_stop)
                    to_code = _get_station_code(to_stop)
                except AttributeError as e:
                    logger.error(f"Failed to get station code: {e}")
                    continue

                # Skip if this is the user's origin (they're already there)
                if user_origin and to_code == user_origin:
                    logger.debug(f"Skipping {to_code} - user's origin station")
                    continue

                # Skip if already departed
                if getattr(to_stop, 'has_departed_station', False):
                    logger.debug(f"Skipping {to_code} - already departed")
                    continue

                # Get transit time for this segment
                try:
                    transit_data = await self._get_segment_transit_time(
                        db,
                        from_code,
                        to_code,
                        journey.data_source or "NJT",
                        journey.line_code,
                    )
                except Exception as e:
                    logger.error(f"Failed to get transit data: {e}", exc_info=True)
                    transit_data = None

                if transit_data is None:
                    logger.debug(
                        f"No transit data for {from_code}→{to_code} "
                        f"(need {self.MIN_SAMPLES} samples, lookback {self.LOOKBACK_HOURS}h)"
                    )
                    # Clear prediction and try to reset baseline
                    to_stop.predicted_arrival = None
                    to_stop.predicted_arrival_samples = 0
                    predicted_time = self._get_scheduled_time(to_stop, "departure")
                    continue

                # Calculate predicted arrival
                predicted_time = predicted_time + timedelta(minutes=transit_data["avg"])
                
                # Validate prediction is reasonable (not in the past)
                predicted_time = self._validate_prediction_time(predicted_time, to_stop)
                
                if predicted_time is None:
                    logger.debug(f"Prediction validation failed for {to_code}")
                    continue  # Skip if validation failed
                
                # Store the prediction
                to_stop.predicted_arrival = predicted_time
                to_stop.predicted_arrival_samples = transit_data["samples"]
                predictions_made += 1

                # Update baseline for next segment (include dwell time)
                predicted_time = self._calculate_next_departure(to_stop, predicted_time)

                logger.debug(
                    f"✅ Prediction: {to_code} at {to_stop.predicted_arrival.isoformat()} "
                    f"({transit_data['samples']} samples, {transit_data['avg']:.1f}min)"
                )
            
            logger.info(
                "🎯 Direct arrival prediction complete",
                train_id=journey.train_id,
                predictions_made=predictions_made,
                segments_processed=segments_processed,
                total_stops=len(stops),
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error in add_predictions_to_stops: {e}",
                exc_info=True,
                train_id=journey.train_id if journey else None,
            )

    async def _get_segment_transit_time(
        self, 
        db: AsyncSession, 
        from_station: str, 
        to_station: str, 
        data_source: str,
        line_code: str | None = None,
    ) -> dict[str, float] | None:
        """
        Calculate transit time directly from recent journeys.
        
        This replaces the need for segment_transit_times table by
        querying journey_stops directly for trains that traveled
        between these two stations.
        
        Returns:
            Dict with 'avg' and 'samples' keys, or None if insufficient data
        """
        cutoff_time = now_et() - timedelta(hours=self.LOOKBACK_HOURS)
        
        # More efficient query: find journeys that have BOTH stations
        # We'll do this with a subquery to ensure we only get relevant journeys
        journey_ids_subquery = (
            select(JourneyStop.journey_id)
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    TrainJourney.data_source == data_source,
                    TrainJourney.last_updated_at >= cutoff_time,
                    JourneyStop.station_code.in_([from_station, to_station]),
                )
            )
            .group_by(JourneyStop.journey_id)
            .having(func.count(distinct(JourneyStop.station_code)) == 2)  # Must have both stations
        )
        
        # Add line filter if provided
        if line_code:
            journey_ids_subquery = journey_ids_subquery.where(TrainJourney.line_code == line_code)
        
        # Now get the actual stops for these journeys
        stmt = (
            select(
                JourneyStop.journey_id,
                JourneyStop.station_code,
                JourneyStop.stop_sequence,
                JourneyStop.actual_departure,
                JourneyStop.scheduled_departure,
                JourneyStop.actual_arrival,
                JourneyStop.scheduled_arrival,
            )
            .where(
                and_(
                    JourneyStop.journey_id.in_(journey_ids_subquery),
                    JourneyStop.station_code.in_([from_station, to_station]),
                )
            )
            .order_by(JourneyStop.journey_id, JourneyStop.stop_sequence)
        )
        
        result = await db.execute(stmt)
        stops_by_journey = {}
        
        # Group stops by journey (simplified since we only get relevant stops)
        for row in result:
            if row.journey_id not in stops_by_journey:
                stops_by_journey[row.journey_id] = []
            stops_by_journey[row.journey_id].append(row)
        
        # Calculate transit times for each journey
        transit_times = []
        
        for journey_id, stops in stops_by_journey.items():
            # Should have exactly 2 stops
            if len(stops) != 2:
                logger.debug(f"Journey {journey_id} has {len(stops)} stops, expected 2")
                continue
                
            # Sort by sequence to ensure correct order
            stops.sort(key=lambda s: s.stop_sequence)
            
            # Verify correct order (from_station should come before to_station)
            if stops[0].station_code == from_station and stops[1].station_code == to_station:
                from_stop = stops[0]
                to_stop = stops[1]
                
                # Use COALESCE logic: actual times if available, otherwise scheduled
                departure = from_stop.actual_departure or from_stop.scheduled_departure
                arrival = to_stop.actual_arrival or to_stop.scheduled_arrival
                
                if departure and arrival:
                    # Calculate time difference
                    delta = ensure_timezone_aware(arrival) - ensure_timezone_aware(departure)
                    minutes = delta.total_seconds() / 60.0
                    
                    # Validate the time is reasonable (positive and not too long)
                    if 0 < minutes <= self.MAX_SEGMENT_MINUTES:
                        transit_times.append(minutes)
                        logger.debug(
                            f"Found transit time: {from_station}→{to_station} = {minutes:.1f}min "
                            f"(journey {journey_id})"
                        )
                    else:
                        logger.debug(
                            f"Skipped unreasonable time: {minutes:.1f}min for {from_station}→{to_station}"
                        )
        
        # Check if we have enough samples
        if len(transit_times) >= self.MIN_SAMPLES:
            return {
                "avg": statistics.median(transit_times),  # Use median for robustness
                "samples": len(transit_times),
            }
        
        logger.debug(
            "insufficient_samples",
            from_station=from_station,
            to_station=to_station,
            samples_found=len(transit_times),
            min_required=self.MIN_SAMPLES,
        )
        return None

    def _determine_starting_point(
        self, 
        stops: list[Any], 
        user_origin: str | None
    ) -> tuple[int | None, Any | None]:
        """
        Determine where to start making predictions and what the initial time is.
        
        Priority order:
        1. User's origin station (if provided)
        2. Last departed stop (if train is in progress)
        3. First stop (if train hasn't started)
        
        Returns:
            Tuple of (start_index, predicted_time) or (None, None) if cannot determine
        """
        # Check for user origin
        if user_origin:
            for i, stop in enumerate(stops):
                if _get_station_code(stop) == user_origin:
                    # Start from user's origin with its scheduled time (plus any delay)
                    base_time = self._get_scheduled_time(stop, "departure")
                    if base_time:
                        # Add any accumulated delay from train progress
                        delay = self._calculate_current_delay(stops)
                        return i, base_time + delay
                    return i, now_et()
        
        # Find last departed stop
        for i in range(len(stops) - 1, -1, -1):
            stop = stops[i]
            if stop.has_departed_station:
                # Use actual departure if available, otherwise scheduled + buffer
                if stop.actual_departure:
                    return i, ensure_timezone_aware(stop.actual_departure)
                else:
                    base_time = self._get_scheduled_time(stop, "departure")
                    if base_time:
                        buffer = self._get_departure_buffer(stop)
                        return i, base_time + buffer
        
        # Default to first stop
        if stops:
            first_stop_time = self._get_scheduled_time(stops[0], "departure")
            if first_stop_time:
                return 0, first_stop_time
        
        return None, None
    
    def _get_scheduled_time(self, stop: Any, time_type: str = "departure") -> Any | None:
        """
        Get scheduled time from a stop object.
        
        Args:
            stop: Stop object
            time_type: "departure" or "arrival"
            
        Returns:
            Timezone-aware datetime or None
        """
        attr_name = f"scheduled_{time_type}"
        if hasattr(stop, attr_name):
            time_value = getattr(stop, attr_name)
            if time_value:
                return ensure_timezone_aware(time_value)
        return None
    
    def _validate_prediction_time(
        self, 
        predicted_time: Any, 
        stop: Any
    ) -> Any | None:
        """
        Validate that a prediction time is reasonable.
        
        Rules:
        - Not too far in the past (>10 minutes)
        - If slightly in past (<10 minutes), use current time
        
        Returns:
            Validated time or None if invalid
        """
        current_time = now_et()
        
        if predicted_time < current_time:
            delay_minutes = (current_time - predicted_time).total_seconds() / 60.0
            
            if delay_minutes > self.STALE_PREDICTION_MINUTES:
                # Too stale - reset to scheduled time if available
                logger.debug(
                    f"Prediction for {_get_station_code(stop)} is {delay_minutes:.0f}min stale, skipping"
                )
                stop.predicted_arrival = None
                stop.predicted_arrival_samples = 0
                return self._get_scheduled_time(stop, "departure")
            else:
                # Slightly stale - use current time
                logger.debug(
                    f"Prediction for {_get_station_code(stop)} is {delay_minutes:.0f}min stale, using current time"
                )
                return current_time
        
        return predicted_time
    
    def _calculate_next_departure(self, stop: Any, arrival_time: Any) -> Any:
        """
        Calculate when train will depart from a stop (for next segment).
        
        Uses scheduled departure time if available and later than arrival.
        Otherwise uses arrival time (assumes minimal dwell).
        
        Returns:
            Departure time for next segment calculation
        """
        scheduled_dep = self._get_scheduled_time(stop, "departure")
        
        if scheduled_dep and scheduled_dep > arrival_time:
            # Use scheduled departure (includes dwell time)
            return scheduled_dep
        else:
            # Use arrival time (minimal or no dwell)
            return arrival_time
    
    def _calculate_current_delay(self, stops: list[Any]) -> timedelta:
        """
        Calculate current delay based on departed stops.
        
        Finds the most recent departed stop with actual times
        and calculates delay vs scheduled time.
        
        Returns:
            Delay timedelta (can be negative for early trains)
        """
        for stop in reversed(stops):
            if stop.has_departed_station:
                if stop.actual_departure:
                    scheduled = self._get_scheduled_time(stop, "departure")
                    if scheduled:
                        actual = ensure_timezone_aware(stop.actual_departure)
                        return actual - scheduled
        
        return timedelta(0)  # No delay if no departed stops
    
    def _get_departure_buffer(self, stop: Any) -> timedelta:
        """
        Get time buffer for inferred departures based on source.
        
        Different inference methods have different confidence levels:
        - api_explicit: Most confident (1 minute buffer)
        - sequential_inference: Medium confidence (2 minute buffer)  
        - time_inference: Least confident (5 minute buffer)
        """
        departure_source = getattr(stop, "departure_source", None)
        
        buffer_map = {
            "api_explicit": 1,
            "sequential_inference": 2,
            "time_inference": 5,
        }
        
        minutes = buffer_map.get(departure_source, 0)
        return timedelta(minutes=minutes)
