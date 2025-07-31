"""
Journey prediction service for arrival time estimates.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models import TrainJourney
from trackrat.services.recent_trains import RecentTrainAnalyzer
from trackrat.utils.time import now_et

logger = get_logger(__name__)


class PredictionResult:
    """Result of an arrival prediction."""

    def __init__(
        self,
        journey_id: int,
        target_station: str,
        predicted_arrival: datetime,
        confidence_score: float,
        based_on_trains: list[str],
        method: str = "recent_similar_trains",
    ):
        self.journey_id = journey_id
        self.target_station = target_station
        self.predicted_arrival = predicted_arrival
        self.confidence_score = confidence_score
        self.based_on_trains = based_on_trains
        self.method = method


class JourneyPredictor:
    """Predicts arrival times based on recent similar trains."""

    def __init__(self) -> None:
        self.recent_trains = RecentTrainAnalyzer()

    async def predict_arrival(
        self, db: AsyncSession, journey: TrainJourney, target_station: str
    ) -> PredictionResult | None:
        """
        Predict arrival time at target station based on recent trains.

        Args:
            db: Database session
            journey: The journey to predict for
            target_station: Station code to predict arrival at

        Returns:
            PredictionResult or None if prediction not possible
        """
        # Find current position
        current_position = self._get_current_position(journey)
        if not current_position:
            logger.debug("no_current_position", journey_id=journey.id)
            return None

        # If already at or past target station, no prediction needed
        completed_stations = current_position.get("completed_stations", [])
        if completed_stations and target_station in completed_stations:
            return None

        # Get recent similar trains
        if not current_position.get("next_station"):
            return self._fallback_prediction(journey, target_station, current_position)

        next_station = current_position.get("next_station")
        if not next_station or not journey.data_source:
            return self._fallback_prediction(journey, target_station, current_position)

        similar_trains = await self.recent_trains.get_recent_similar_trains(
            db,
            next_station,
            target_station,
            journey.data_source,
            hours_back=6,
        )

        if not similar_trains:
            logger.debug(
                "no_similar_trains",
                journey_id=journey.id,
                from_station=current_position["next_station"],
                to_station=target_station,
            )
            return self._fallback_prediction(journey, target_station, current_position)

        # Calculate expected time based on recent trains
        segment_times = []
        train_ids = []

        for train in similar_trains[:5]:  # Use up to 5 most recent
            time_taken = self.recent_trains.calculate_segment_time(
                train, current_position["next_station"], target_station
            )
            if time_taken:
                segment_times.append(time_taken)
                if train.train_id is not None:
                    train_ids.append(train.train_id)

        if not segment_times:
            return self._fallback_prediction(journey, target_station, current_position)

        # Use median for robustness against outliers
        segment_times.sort()
        median_time = segment_times[len(segment_times) // 2]

        # Calculate prediction
        predicted_arrival = now_et() + timedelta(minutes=median_time)

        # Calculate confidence based on consistency
        if len(segment_times) >= 3:
            # Simple confidence calculation based on variance
            avg_time = sum(segment_times) / len(segment_times)
            variance = sum((t - avg_time) ** 2 for t in segment_times) / len(
                segment_times
            )
            std_dev = variance**0.5

            # High confidence if times are consistent (low std dev relative to median)
            if median_time > 0:
                confidence = max(0.5, min(0.95, 1.0 - (std_dev / median_time)))
            else:
                confidence = 0.5
        else:
            confidence = 0.6  # Lower confidence with fewer samples

        # Update journey progress with prediction
        await self._update_journey_progress_prediction(
            db, journey, predicted_arrival, confidence, train_ids
        )

        if journey.id is None:
            return None

        return PredictionResult(
            journey_id=journey.id,
            target_station=target_station,
            predicted_arrival=predicted_arrival,
            confidence_score=confidence,
            based_on_trains=train_ids,
            method="recent_similar_trains",
        )

    def _get_current_position(self, journey: TrainJourney) -> dict[str, Any] | None:
        """Get current position and status of the journey."""
        if not journey.stops:
            return None

        sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

        last_departed_station = None
        next_station = None
        completed_stations = []

        for stop in sorted_stops:
            if stop.has_departed_station:
                last_departed_station = stop.station_code
                completed_stations.append(stop.station_code)
            else:
                next_station = stop.station_code
                break

        # If all stops departed, train is at terminal
        if not next_station and sorted_stops:
            last_departed_station = sorted_stops[-1].station_code

        return {
            "last_departed_station": last_departed_station,
            "next_station": next_station,
            "completed_stations": completed_stations,
        }

    def _fallback_prediction(
        self,
        journey: TrainJourney,
        target_station: str,
        current_position: dict[str, Any],
    ) -> PredictionResult | None:
        """Simple fallback prediction based on schedule."""
        # Find the target stop
        target_stop = None
        for stop in journey.stops:
            if stop.station_code == target_station:
                target_stop = stop
                break

        if not target_stop or not target_stop.scheduled_arrival:
            return None

        # Get current delay
        current_delay = 0
        if journey.progress_snapshots:
            # Filter out entries with None captured_at
            valid_snapshots = [
                p for p in journey.progress_snapshots if p.captured_at is not None
            ]
            if valid_snapshots:
                latest_progress = max(
                    valid_snapshots, key=lambda p: p.captured_at or datetime.min
                )
                current_delay = latest_progress.total_delay_minutes or 0

        # Simple prediction: scheduled time + current delay
        predicted_arrival = target_stop.scheduled_arrival + timedelta(
            minutes=current_delay
        )

        if journey.id is None:
            return None

        return PredictionResult(
            journey_id=journey.id,
            target_station=target_station,
            predicted_arrival=predicted_arrival,
            confidence_score=0.5,  # Low confidence for fallback
            based_on_trains=[],
            method="schedule_with_delay",
        )

    async def _update_journey_progress_prediction(
        self,
        db: AsyncSession,
        journey: TrainJourney,
        predicted_arrival: datetime,
        confidence: float,
        based_on_trains: list[str],
    ) -> None:
        """Update the latest journey progress with prediction info."""
        # Find the most recent progress record
        if journey.progress_snapshots:
            # Filter out entries with None captured_at
            valid_snapshots = [
                p for p in journey.progress_snapshots if p.captured_at is not None
            ]
            if valid_snapshots:
                latest_progress = max(
                    valid_snapshots, key=lambda p: p.captured_at or datetime.min
                )
                latest_progress.predicted_arrival = predicted_arrival
                latest_progress.prediction_confidence = float(confidence)  # type: ignore[assignment]
                latest_progress.prediction_based_on = json.dumps(based_on_trains)

            logger.debug(
                "updated_progress_with_prediction",
                journey_id=journey.id,
                predicted_arrival=predicted_arrival.isoformat(),
                confidence=confidence,
            )
