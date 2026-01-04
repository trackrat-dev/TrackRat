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

from trackrat.config.station_configs import get_tracks_for_station
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

        # NY Penn platform mappings (tracks that share the same platform)
        self.ny_platform_mappings = {
            "1 & 2": ["1", "2"],
            "3 & 4": ["3", "4"],
            "5 & 6": ["5", "6"],
            "7 & 8": ["7", "8"],
            "9 & 10": ["9", "10"],
            "11 & 12": ["11", "12"],
            "13 & 14": ["13", "14"],
            "15 & 16": ["15", "16"],
            "17": ["17"],
            "18 & 19": ["18", "19"],
            "20 & 21": ["20", "21"],
        }

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

        # Step 5: Convert tracks to platforms for NY Penn
        platform_probs = self._convert_tracks_to_platforms(
            normalized_probs, station_code
        )

        # Step 6: Get top platforms (for compatibility, though iOS doesn't use these)
        sorted_platforms = sorted(
            platform_probs.items(), key=lambda x: x[1], reverse=True
        )

        primary_platform = sorted_platforms[0][0] if sorted_platforms else "Unknown"
        confidence = sorted_platforms[0][1] if sorted_platforms else 0.0
        top_3_platforms = [platform for platform, _ in sorted_platforms[:3]]

        # Step 7: Build response with platform probabilities
        return {
            "platform_probabilities": platform_probs,  # Now contains platforms, not tracks
            "primary_prediction": primary_platform,  # Platform name for compatibility
            "confidence": confidence,  # Keep for compatibility
            "top_3": top_3_platforms,  # Platform names for compatibility
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

        # Convert tracks to platforms for NY Penn
        platform_probs = self._convert_tracks_to_platforms(probabilities, station_code)

        # Sort by probability to get top predictions
        sorted_platforms = sorted(
            platform_probs.items(), key=lambda x: x[1], reverse=True
        )

        primary_platform = sorted_platforms[0][0] if sorted_platforms else "Unknown"
        confidence = sorted_platforms[0][1] if sorted_platforms else 0.0
        top_3_platforms = [platform for platform, _ in sorted_platforms[:3]]

        return {
            "platform_probabilities": platform_probs,  # Now contains platforms
            "primary_prediction": primary_platform,
            "confidence": confidence,
            "top_3": top_3_platforms,
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

        # Get tracks from station configuration
        tracks = get_tracks_for_station(station_code)
        if not tracks:
            # Generic fallback if station has no track config
            tracks = [str(i) for i in range(1, 11)]  # Tracks 1-10

        uniform_prob = 1.0 / len(tracks)
        track_probabilities = {track: uniform_prob for track in tracks}

        # Convert tracks to platforms
        platform_probs = self._convert_tracks_to_platforms(
            track_probabilities, station_code
        )

        # Get top platforms
        sorted_platforms = sorted(
            platform_probs.items(), key=lambda x: x[1], reverse=True
        )
        primary_platform = sorted_platforms[0][0] if sorted_platforms else "Unknown"
        top_3_platforms = [platform for platform, _ in sorted_platforms[:3]]

        return {
            "platform_probabilities": platform_probs,  # Platforms, not tracks
            "primary_prediction": primary_platform,
            "confidence": uniform_prob,
            "top_3": top_3_platforms,
            "model_version": "historical_v1_uniform",
            "features_used": {
                "prediction_level": "uniform_fallback",
                "historical_records": 0,
                "station_code": station_code,
            },
        }

    def _convert_tracks_to_platforms(
        self, track_probabilities: dict[str, float], station_code: str
    ) -> dict[str, float]:
        """
        Convert individual track probabilities to platform probabilities.

        For NY Penn, tracks are grouped into platforms (e.g., tracks 1 & 2 share a platform).
        For other stations, return tracks as-is since they don't have platform groupings.

        Args:
            track_probabilities: Dictionary of track -> probability
            station_code: Station code (e.g., 'NY')

        Returns:
            Dictionary of platform -> probability
        """
        # Only NY Penn has platform groupings
        if station_code != "NY":
            # For non-NY stations, each track is its own "platform"
            return track_probabilities

        # Convert tracks to platforms for NY Penn
        platform_probabilities = {}

        for platform_name, tracks in self.ny_platform_mappings.items():
            # Sum probabilities for all tracks in this platform
            total_prob = 0.0
            for track in tracks:
                if track in track_probabilities:
                    total_prob += track_probabilities[track]

            # Only add platform if it has non-zero probability
            if total_prob > 0:
                platform_probabilities[platform_name] = total_prob

        return platform_probabilities


# Create singleton instance
historical_track_predictor = HistoricalTrackPredictor()
