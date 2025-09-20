"""
Simplified historical track prediction service.

Uses hierarchical historical data to predict tracks with high accuracy.
No ML models required - just SQL queries and simple logic.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.track_occupancy import TrackOccupancyService

logger = get_logger(__name__)

# Configuration thresholds
MIN_TRAIN_ID_RECORDS = 10  # Need at least 10 historical records for train ID
MIN_LINE_CODE_RECORDS = 25  # Need at least 25 historical records for line code
MIN_SERVICE_PROVIDER_RECORDS = (
    250  # Need at least 250 historical records for service provider
)


class HistoricalTrackPredictor:
    """
    Simplified track prediction using historical patterns.

    Hierarchical approach:
    1. Try exact train ID (if >= 10 records)
    2. Fallback to line code (if >= 25 records)
    3. Fallback to service provider (if >= 250 records)
    4. Fallback to static distribution (configurable values)

    Then remove occupied tracks and renormalize probabilities.
    """

    def __init__(self) -> None:
        """Initialize the predictor."""
        self.occupancy_service = TrackOccupancyService()

    async def predict_track(
        self,
        station_code: str,
        train_id: str,
        line_code: str | None,
        data_source: str,
        scheduled_departure: datetime,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Predict track assignment using historical data.

        Args:
            station_code: Station code (e.g., 'NY')
            train_id: Train identifier (e.g., '3427')
            line_code: Line code (e.g., 'No', 'Mo')
            data_source: Service provider ('NJT' or 'AMTRAK')
            scheduled_departure: When the train is scheduled to depart
            db: Database session

        Returns:
            Dictionary with track probabilities and metadata
        """

        logger.info(
            "historical_prediction_start",
            station_code=station_code,
            train_id=train_id,
            line_code=line_code,
            data_source=data_source,
        )

        # Step 1: Get historical track distributions at each level
        train_id_dist = await self._get_train_id_distribution(
            db, station_code, train_id
        )

        line_code_dist = None
        if line_code:
            line_code_dist = await self._get_line_code_distribution(
                db, station_code, line_code
            )

        service_dist = await self._get_service_distribution(
            db, station_code, data_source
        )

        # Step 2: Choose which distribution to use (hierarchical)
        selected_dist = None
        prediction_level = None

        if train_id_dist and train_id_dist["total_records"] >= MIN_TRAIN_ID_RECORDS:
            selected_dist = train_id_dist
            prediction_level = "train_id"
            logger.info(
                "using_train_id_prediction",
                train_id=train_id,
                records=train_id_dist["total_records"],
            )
        elif (
            line_code_dist and line_code_dist["total_records"] >= MIN_LINE_CODE_RECORDS
        ):
            selected_dist = line_code_dist
            prediction_level = "line_code"
            logger.info(
                "using_line_code_prediction",
                line_code=line_code,
                records=line_code_dist["total_records"],
            )
        elif (
            service_dist
            and service_dist["total_records"] >= MIN_SERVICE_PROVIDER_RECORDS
        ):
            selected_dist = service_dist
            prediction_level = "service_provider"
            logger.info(
                "using_service_prediction",
                data_source=data_source,
                records=service_dist["total_records"],
            )
        else:
            # Use static distribution as final fallback
            logger.info(
                "using_static_fallback",
                station_code=station_code,
                train_id=train_id,
                service_records=service_dist["total_records"] if service_dist else 0,
                reason="insufficient_historical_data",
            )
            return self._create_static_distribution(station_code, data_source)

        # This shouldn't happen since we always have a fallback, but keep for safety
        if not selected_dist or not selected_dist["track_probabilities"]:
            logger.warning(
                "unexpected_no_distribution",
                station_code=station_code,
                train_id=train_id,
            )
            return self._create_static_distribution(station_code, data_source)

        # Step 3: Get occupied tracks
        occupied_response = await self.occupancy_service.get_occupied_tracks(
            station_code
        )
        occupied_tracks = set(occupied_response.occupied_tracks)

        logger.info(
            "occupied_tracks_fetched",
            station_code=station_code,
            count=len(occupied_tracks),
            tracks=list(occupied_tracks),
        )

        # Step 4: Remove occupied tracks and renormalize
        available_probs = {}
        for track, prob in selected_dist["track_probabilities"].items():
            if track not in occupied_tracks:
                available_probs[track] = prob

        # Renormalize so probabilities sum to 1.0
        total_available_prob = sum(available_probs.values())
        if total_available_prob > 0:
            normalized_probs = {
                track: prob / total_available_prob
                for track, prob in available_probs.items()
            }
        else:
            # All historical tracks are occupied - return static fallback
            logger.warning(
                "all_historical_tracks_occupied",
                station_code=station_code,
                historical_tracks=list(selected_dist["track_probabilities"].keys()),
                occupied_tracks=list(occupied_tracks),
            )
            return self._create_static_distribution(station_code, data_source)

        # Step 5: Get top predictions
        sorted_tracks = sorted(
            normalized_probs.items(), key=lambda x: x[1], reverse=True
        )

        primary_track = sorted_tracks[0][0] if sorted_tracks else None
        confidence = sorted_tracks[0][1] if sorted_tracks else 0.0
        top_3 = [track for track, _ in sorted_tracks[:3]]

        # Step 6: Build response
        return {
            "platform_probabilities": normalized_probs,
            "primary_prediction": primary_track,
            "confidence": confidence,
            "top_3": top_3,
            "model_version": f"historical_v1_{prediction_level}",
            "features_used": {
                "prediction_level": prediction_level,
                "historical_records": selected_dist["total_records"],
                "unique_tracks_in_history": len(selected_dist["track_probabilities"]),
                "occupied_tracks_removed": len(occupied_tracks),
                "train_id": train_id,
                "line_code": line_code,
                "data_source": data_source,
                "station_code": station_code,
            },
        }

    async def _get_train_id_distribution(
        self, db: AsyncSession, station_code: str, train_id: str
    ) -> dict[str, Any] | None:
        """Get track distribution for specific train ID."""

        # Query historical track assignments for this train
        query = (
            select(JourneyStop.track, func.count(JourneyStop.id).label("count"))
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.train_id == train_id,
                    JourneyStop.track.is_not(None),
                )
            )
            .group_by(JourneyStop.track)
            .order_by(func.count(JourneyStop.id).desc())
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return None

        total = sum(row[1] for row in rows)
        probabilities = {row[0]: row[1] / total for row in rows}

        logger.debug(
            "train_id_distribution",
            train_id=train_id,
            total_records=total,
            unique_tracks=len(probabilities),
        )

        return {"track_probabilities": probabilities, "total_records": total}

    async def _get_line_code_distribution(
        self, db: AsyncSession, station_code: str, line_code: str
    ) -> dict[str, Any] | None:
        """Get track distribution for trains on this line."""

        query = (
            select(JourneyStop.track, func.count(JourneyStop.id).label("count"))
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.line_code == line_code,
                    JourneyStop.track.is_not(None),
                )
            )
            .group_by(JourneyStop.track)
            .order_by(func.count(JourneyStop.id).desc())
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return None

        total = sum(row[1] for row in rows)
        probabilities = {row[0]: row[1] / total for row in rows}

        logger.debug(
            "line_code_distribution",
            line_code=line_code,
            total_records=total,
            unique_tracks=len(probabilities),
        )

        return {"track_probabilities": probabilities, "total_records": total}

    async def _get_service_distribution(
        self, db: AsyncSession, station_code: str, data_source: str
    ) -> dict[str, Any] | None:
        """Get track distribution for service provider."""

        query = (
            select(JourneyStop.track, func.count(JourneyStop.id).label("count"))
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.data_source == data_source,
                    JourneyStop.track.is_not(None),
                )
            )
            .group_by(JourneyStop.track)
            .order_by(func.count(JourneyStop.id).desc())
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return None

        total = sum(row[1] for row in rows)
        probabilities = {row[0]: row[1] / total for row in rows}

        logger.debug(
            "service_distribution",
            data_source=data_source,
            total_records=total,
            unique_tracks=len(probabilities),
        )

        return {"track_probabilities": probabilities, "total_records": total}

    def _create_static_distribution(
        self, station_code: str, data_source: str
    ) -> dict[str, Any]:
        """
        Create static distribution based on configured values.

        This is the final fallback when we don't have enough historical data
        even at the service provider level (< 250 records).
        """

        # Static distributions based on historical data
        # Raw counts: NJT = [536,602,629,546,12,77,211,157,236,262,210,226,289,64,37,5,0,0,0,0,0]
        #           Amtrak = [0,0,2,0,213,187,146,217,142,170,165,214,165,419,179,22,0,0,0,0,2]

        # Calculate probabilities from raw counts
        njt_counts = [
            536,
            602,
            629,
            546,
            12,
            77,
            211,
            157,
            236,
            262,
            210,
            226,
            289,
            64,
            37,
            5,
            0,
            0,
            0,
            0,
            0,
        ]
        njt_total = sum(njt_counts)
        njt_probs = {}
        for i, count in enumerate(njt_counts, 1):
            if count > 0:  # Only include tracks with non-zero probability
                njt_probs[str(i)] = count / njt_total

        amtrak_counts = [
            0,
            0,
            2,
            0,
            213,
            187,
            146,
            217,
            142,
            170,
            165,
            214,
            165,
            419,
            179,
            22,
            0,
            0,
            0,
            0,
            2,
        ]
        amtrak_total = sum(amtrak_counts)
        amtrak_probs = {}
        for i, count in enumerate(amtrak_counts, 1):
            if count > 0:  # Only include tracks with non-zero probability
                amtrak_probs[str(i)] = count / amtrak_total

        static_distributions = {
            "NY": {"NJT": njt_probs, "AMTRAK": amtrak_probs}
            # Other stations can be added here
        }

        # Get static distribution for this station and service
        if station_code in static_distributions:
            if data_source in static_distributions[station_code]:
                probabilities = static_distributions[station_code][data_source]
            else:
                # Fallback to uniform if service not configured
                return self._create_uniform_distribution(station_code)
        else:
            # Fallback to uniform if station not configured
            return self._create_uniform_distribution(station_code)

        # Sort by probability to get top predictions
        sorted_tracks = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)

        primary_track = sorted_tracks[0][0] if sorted_tracks else None
        confidence = sorted_tracks[0][1] if sorted_tracks else 0.0
        top_3 = [track for track, _ in sorted_tracks[:3]]

        return {
            "platform_probabilities": probabilities,
            "primary_prediction": primary_track,
            "confidence": confidence,
            "top_3": top_3,
            "model_version": "historical_v1_static",
            "features_used": {
                "prediction_level": "static_fallback",
                "historical_records": 0,
                "station_code": station_code,
                "data_source": data_source,
            },
        }

    def _create_uniform_distribution(self, station_code: str) -> dict[str, Any]:
        """Create uniform distribution when no data available."""

        # Default tracks for NY Penn (most complex station)
        # In production, this would come from station configuration
        if station_code == "NY":
            tracks = [str(i) for i in range(1, 16)]  # Tracks 1-15
        else:
            # Generic fallback
            tracks = [str(i) for i in range(1, 11)]  # Tracks 1-10

        uniform_prob = 1.0 / len(tracks)
        probabilities = {track: uniform_prob for track in tracks}

        return {
            "platform_probabilities": probabilities,
            "primary_prediction": tracks[0],
            "confidence": uniform_prob,
            "top_3": tracks[:3],
            "model_version": "historical_v1_uniform",
            "features_used": {
                "prediction_level": "uniform_fallback",
                "historical_records": 0,
                "station_code": station_code,
            },
        }


# Create singleton instance
historical_track_predictor = HistoricalTrackPredictor()
