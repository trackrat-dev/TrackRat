"""
Direct arrival time forecaster without intermediate segment storage.

This service calculates segment times directly from recent journeys,
eliminating the need for the segment_transit_times table entirely.
It queries journey_stops directly to find how long recent trains took.
"""

import statistics
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.sql.functions import coalesce
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
    MIN_SAMPLES = 3  # Minimum trains needed for a prediction (increased for better reliability)
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
            start_index, predicted_time = self._determine_starting_point(
                stops, user_origin
            )

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
                if getattr(to_stop, "has_departed_station", False):
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

                if predicted_time is None:
                    logger.debug(f"No valid baseline time to predict for {to_code}")
                    to_stop.predicted_arrival = None
                    to_stop.predicted_arrival_samples = 0
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
        Calculate transit time from segments that completed recently.
        
        A segment is considered "recent" if the arrival at the destination
        station occurred within LOOKBACK_HOURS.

        Returns:
            Dict with 'avg' and 'samples' keys, or None if insufficient data
        """
        cutoff_time = now_et() - timedelta(hours=self.LOOKBACK_HOURS)

        # Single query that gets segment data and filters on arrival time
        stmt = (
            select(
                JourneyStop.journey_id,
                func.min(case(
                    (JourneyStop.station_code == from_station, JourneyStop.stop_sequence)
                )).label('from_sequence'),
                func.max(case(
                    (JourneyStop.station_code == from_station,
                     coalesce(JourneyStop.actual_departure, JourneyStop.scheduled_departure))
                )).label('departure_time'),
                func.max(case(
                    (JourneyStop.station_code == to_station, JourneyStop.stop_sequence)
                )).label('to_sequence'),
                func.max(case(
                    (JourneyStop.station_code == to_station,
                     coalesce(JourneyStop.actual_arrival, JourneyStop.scheduled_arrival))
                )).label('arrival_time'),
            )
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    TrainJourney.data_source == data_source,
                    JourneyStop.station_code.in_([from_station, to_station]),
                )
            )
            .group_by(JourneyStop.journey_id)
            .having(
                and_(
                    func.count(distinct(JourneyStop.station_code)) == 2,
                    # Ensure from comes before to
                    func.min(case((JourneyStop.station_code == from_station, JourneyStop.stop_sequence))) <
                    func.max(case((JourneyStop.station_code == to_station, JourneyStop.stop_sequence))),
                    # Key change: Filter on actual segment completion time
                    func.max(case(
                        (JourneyStop.station_code == to_station,
                         coalesce(JourneyStop.actual_arrival, JourneyStop.scheduled_arrival))
                    )) >= cutoff_time
                )
            )
        )

        # Add line filter if provided
        if line_code:
            stmt = stmt.where(TrainJourney.line_code == line_code)

        result = await db.execute(stmt)
        transit_times = []

        for row in result:
            if row.departure_time and row.arrival_time:
                delta = ensure_timezone_aware(row.arrival_time) - ensure_timezone_aware(row.departure_time)
                minutes = delta.total_seconds() / 60.0

                # Validate the time is reasonable (positive and not too long)
                if 0 < minutes <= self.MAX_SEGMENT_MINUTES:
                    transit_times.append(minutes)
                    logger.debug(
                        f"Found recent segment: {from_station}→{to_station} = {minutes:.1f}min "
                        f"(arrived {row.arrival_time})"
                    )
                else:
                    logger.debug(
                        f"Skipped unreasonable time: {minutes:.1f}min for {from_station}→{to_station}"
                    )

        # Check if we have enough samples
        if len(transit_times) >= self.MIN_SAMPLES:
            return {
                "avg": statistics.median(transit_times),
                "samples": len(transit_times),
            }

        logger.debug(
            f"Insufficient recent segments for {from_station}→{to_station}: "
            f"found {len(transit_times)}, need {self.MIN_SAMPLES}"
        )
        return None

    def _determine_starting_point(
        self, stops: list[Any], user_origin: str | None
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

    def _get_scheduled_time(
        self, stop: Any, time_type: str = "departure"
    ) -> datetime | None:
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
            if time_value and isinstance(time_value, datetime):
                return ensure_timezone_aware(time_value)
        return None

    def _validate_prediction_time(self, predicted_time: Any, stop: Any) -> Any | None:
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
                    if scheduled and isinstance(stop.actual_departure, datetime):
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
        minutes = 0
        if isinstance(departure_source, str):
            minutes = buffer_map.get(departure_source, 0)
        return timedelta(minutes=minutes)
