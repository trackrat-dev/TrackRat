"""
Direct arrival time forecaster without intermediate segment storage.

This service calculates segment times directly from recent journeys,
eliminating the need for the segment_transit_times table entirely.
It queries journey_stops directly to find how long recent trains took.
"""

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce
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
    MIN_SAMPLES = (
        3  # Minimum trains needed for a prediction (increased for better reliability)
    )
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

            # Collect station codes for batch query
            route_station_codes = []
            for s in stops[start_index:]:
                try:
                    route_station_codes.append(_get_station_code(s))
                except AttributeError as e:
                    logger.error(f"Failed to get station code: {e}")
                    break

            # Batch-fetch all segment transit times in one query
            try:
                all_transit_data = await self._get_all_segment_transit_times(
                    db,
                    route_station_codes,
                    journey.data_source or "NJT",
                    journey.line_code,
                )
            except Exception as e:
                logger.error(
                    f"Failed to batch-fetch transit data: {e}", exc_info=True
                )
                all_transit_data = {}

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

                # Look up pre-fetched transit data for this segment
                transit_data = all_transit_data.get((from_code, to_code))

                if transit_data is None:
                    logger.debug(
                        f"No transit data for {from_code}→{to_code} "
                        f"(need {self.MIN_SAMPLES} samples, lookback {self.LOOKBACK_HOURS}h)"
                    )
                    # No empirical data for this segment. Fall back to scheduled
                    # segment duration to preserve accumulated delay through the gap.
                    to_stop.predicted_arrival = None
                    to_stop.predicted_arrival_samples = 0
                    if predicted_time is not None:
                        scheduled_duration = self._get_scheduled_segment_duration(
                            from_stop, to_stop
                        )
                        if scheduled_duration is not None:
                            predicted_time = predicted_time + scheduled_duration
                            predicted_time = self._calculate_next_departure(
                                to_stop, predicted_time
                            )
                        else:
                            # Can't compute duration — lose the chain
                            predicted_time = self._get_scheduled_time(
                                to_stop, "departure"
                            )
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

    async def _get_all_segment_transit_times(
        self,
        db: AsyncSession,
        station_codes: list[str],
        data_source: str,
        line_code: str | None = None,
    ) -> dict[tuple[str, str], dict[str, float]]:
        """
        Batch-fetch transit times for all consecutive station pairs in one query.

        Instead of N-1 individual queries (one per segment), this fetches all
        relevant stops in a single query and computes segment times in Python.

        Args:
            db: Database session
            station_codes: Ordered list of station codes along the route
            data_source: Train data source (NJT, AMTRAK, etc.)
            line_code: Optional line code filter

        Returns:
            Dict mapping (from_station, to_station) to {"avg": float, "samples": int}.
            Missing pairs (insufficient data) are omitted from the result.
        """
        if len(station_codes) < 2:
            return {}

        cutoff_time = now_et() - timedelta(hours=self.LOOKBACK_HOURS)
        unique_codes = list(dict.fromkeys(station_codes))  # dedupe preserving order

        # Single query: fetch all recent stops at relevant stations
        stmt = (
            select(
                JourneyStop.journey_id,
                JourneyStop.station_code,
                JourneyStop.stop_sequence,
                coalesce(
                    JourneyStop.actual_departure, JourneyStop.scheduled_departure
                ).label("departure_time"),
                coalesce(
                    JourneyStop.actual_arrival, JourneyStop.scheduled_arrival
                ).label("arrival_time"),
            )
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    TrainJourney.data_source == data_source,
                    JourneyStop.station_code.in_(unique_codes),
                    # Narrow scan to recent journeys only
                    TrainJourney.journey_date
                    >= (now_et() - timedelta(days=1)).date(),
                )
            )
        )

        if line_code:
            stmt = stmt.where(TrainJourney.line_code == line_code)

        result = await db.execute(stmt)

        # Group stops by journey_id
        journeys_stops: dict[int, list] = defaultdict(list)
        for row in result:
            journeys_stops[row.journey_id].append(row)

        # For each historical journey, compute transit times for each segment pair
        segment_times: dict[tuple[str, str], list[float]] = defaultdict(list)

        for journey_id, j_stops in journeys_stops.items():
            # Build lookup: station_code -> (first stop for departure, last stop for arrival)
            # This matches the original MIN/MAX semantics for handling duplicate stations
            first_at: dict[str, Any] = {}  # earliest stop_sequence per station
            last_at: dict[str, Any] = {}  # latest stop_sequence per station

            for stop in j_stops:
                code = stop.station_code
                if code not in first_at or stop.stop_sequence < first_at[code].stop_sequence:
                    first_at[code] = stop
                if code not in last_at or stop.stop_sequence > last_at[code].stop_sequence:
                    last_at[code] = stop

            # Check each consecutive pair in the route
            for i in range(len(station_codes) - 1):
                from_code = station_codes[i]
                to_code = station_codes[i + 1]

                from_stop = first_at.get(from_code)
                to_stop = last_at.get(to_code)

                if not from_stop or not to_stop:
                    continue

                # Ensure from comes before to (same as original HAVING clause)
                if from_stop.stop_sequence >= to_stop.stop_sequence:
                    continue

                # Check arrival recency (same as original cutoff filter)
                if not to_stop.arrival_time:
                    continue
                arr_time = ensure_timezone_aware(to_stop.arrival_time)
                if arr_time < cutoff_time:
                    continue

                # Compute transit time
                if not from_stop.departure_time:
                    continue
                dep_time = ensure_timezone_aware(from_stop.departure_time)
                minutes = (arr_time - dep_time).total_seconds() / 60.0

                if 0 < minutes <= self.MAX_SEGMENT_MINUTES:
                    segment_times[(from_code, to_code)].append(minutes)
                    logger.debug(
                        f"Found recent segment: {from_code}→{to_code} = {minutes:.1f}min "
                        f"(arrived {to_stop.arrival_time})"
                    )
                else:
                    logger.debug(
                        f"Skipped unreasonable time: {minutes:.1f}min for {from_code}→{to_code}"
                    )

        # Convert to result format, only including pairs with sufficient samples
        result_dict: dict[tuple[str, str], dict[str, float]] = {}
        for i in range(len(station_codes) - 1):
            pair = (station_codes[i], station_codes[i + 1])
            times = segment_times.get(pair, [])
            if len(times) >= self.MIN_SAMPLES:
                result_dict[pair] = {
                    "avg": statistics.median(times),
                    "samples": len(times),
                }
            else:
                logger.debug(
                    f"Insufficient recent segments for {pair[0]}→{pair[1]}: "
                    f"found {len(times)}, need {self.MIN_SAMPLES}"
                )

        logger.info(
            "Batch segment query complete",
            station_count=len(unique_codes),
            segment_pairs=len(station_codes) - 1,
            segments_with_data=len(result_dict),
            total_journeys_scanned=len(journeys_stops),
        )

        return result_dict

    async def _get_segment_transit_time(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
        line_code: str | None = None,
    ) -> dict[str, float] | None:
        """
        Calculate transit time for a single segment.

        Delegates to the batch method for a single pair.

        Returns:
            Dict with 'avg' and 'samples' keys, or None if insufficient data
        """
        results = await self._get_all_segment_transit_times(
            db, [from_station, to_station], data_source, line_code
        )
        return results.get((from_station, to_station))

    def _determine_starting_point(
        self, stops: list[Any], user_origin: str | None
    ) -> tuple[int | None, Any | None]:
        """
        Determine where to start making predictions and what the initial time is.

        Logic:
        1. If user_origin provided:
           - If train has departed from user's origin: use actual departure time
           - If train hasn't reached user's origin: use scheduled departure time
        2. If no user_origin: find last departed stop for full journey view

        This ensures user journeys use scheduled time until train departs their origin,
        then switch to actual times which naturally incorporate delays.

        Returns:
            Tuple of (start_index, predicted_time) or (None, None) if cannot determine
        """
        # Handle user's origin station
        if user_origin:
            for i, stop in enumerate(stops):
                if _get_station_code(stop) == user_origin:
                    # Check if train has departed from user's origin
                    if getattr(stop, "has_departed_station", False):
                        # Train has departed - use actual time (includes delays naturally)
                        if stop.actual_departure:
                            return i, ensure_timezone_aware(stop.actual_departure)
                        else:
                            # No actual time but marked as departed - use scheduled + buffer
                            base_time = self._get_scheduled_time(stop, "departure")
                            if base_time:
                                buffer = self._get_departure_buffer(stop)
                                return i, base_time + buffer
                            return i, now_et()
                    else:
                        # Train hasn't departed from user's origin - use scheduled time
                        base_time = self._get_scheduled_time(stop, "departure")
                        if base_time:
                            return i, base_time
                        # Fallback if no scheduled time available
                        return i, now_et()

        # No user origin specified - find last departed stop for full journey view
        for i in range(len(stops) - 1, -1, -1):
            stop = stops[i]
            if getattr(stop, "has_departed_station", False):
                # Use actual departure if available, otherwise scheduled + buffer
                if stop.actual_departure:
                    return i, ensure_timezone_aware(stop.actual_departure)
                else:
                    base_time = self._get_scheduled_time(stop, "departure")
                    if base_time:
                        buffer = self._get_departure_buffer(stop)
                        return i, base_time + buffer

        # No departed stops found - cannot make meaningful predictions
        # (This handles the case where train hasn't started journey yet)
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

    def _get_scheduled_segment_duration(
        self, from_stop: Any, to_stop: Any
    ) -> timedelta | None:
        """
        Get the scheduled transit duration between two consecutive stops.

        Uses scheduled departure from from_stop and scheduled arrival at to_stop.
        Returns None if either time is unavailable.
        """
        from_time = self._get_scheduled_time(from_stop, "departure")
        to_time = self._get_scheduled_time(to_stop, "arrival")
        if from_time and to_time and to_time > from_time:
            return to_time - from_time
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
                # Too stale - prediction is clearly wrong for this stop.
                # Use current time as baseline for next segment (preserves
                # implicit delay rather than resetting to schedule).
                logger.debug(
                    f"Prediction for {_get_station_code(stop)} is {delay_minutes:.0f}min stale, skipping"
                )
                stop.predicted_arrival = None
                stop.predicted_arrival_samples = 0
                return current_time
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
