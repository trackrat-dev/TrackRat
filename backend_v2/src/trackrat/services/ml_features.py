"""
Feature extraction service for ML track predictions.

Extracts features from the database needed for track predictions.
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.platform_mappings import get_platform_for_track
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ensure_timezone_aware

logger = get_logger()


class TrackPredictionFeatures:
    """Extract ML features from database for track predictions."""

    async def extract_features(
        self, db: AsyncSession, station_code: str, train_id: str, journey_date: date
    ) -> dict[str, Any] | None:
        """
        Extract features for track prediction.

        Args:
            db: Database session
            station_code: Station code (e.g., 'NY')
            train_id: Train ID (e.g., '3123')
            journey_date: Date of journey

        Returns:
            Dictionary with features:
            - hour_of_day: 0-23
            - day_of_week: 0-6 (0=Monday, 6=Sunday)
            - is_amtrak: 0 or 1
            - line_code: String
            - destination: String
            - minutes_since_track_used: Dict[track -> minutes]
            - minutes_since_platform_used: Dict[platform -> minutes]
            - scheduled_departure: Datetime (for reference)
        """

        # Find the specific journey
        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
            )
        )

        result = await db.execute(stmt)
        journey = result.scalar_one_or_none()

        if not journey:
            logger.warning(
                "journey_not_found", train_id=train_id, journey_date=journey_date
            )
            return None

        # Find the stop at the requested station
        stop_stmt = select(JourneyStop).where(
            and_(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == station_code,
            )
        )

        result = await db.execute(stop_stmt)
        stop = result.scalar_one_or_none()

        if not stop or not stop.scheduled_departure:
            logger.warning(
                "stop_not_found", train_id=train_id, station_code=station_code
            )
            return None

        scheduled_departure = ensure_timezone_aware(stop.scheduled_departure)

        # Extract basic features
        features: dict[str, Any] = {
            "hour_of_day": scheduled_departure.hour,
            "day_of_week": scheduled_departure.weekday(),  # 0=Monday, 6=Sunday
            "is_amtrak": 1 if train_id.startswith("A") else 0,
            "line_code": journey.line_code or "UNKNOWN",
            "destination": journey.destination or "UNKNOWN",
            "scheduled_departure": scheduled_departure,
        }

        # Get time-based track usage features
        track_times = await self._get_minutes_since_track_used(
            db, station_code, scheduled_departure
        )
        platform_times = await self._get_minutes_since_platform_used(
            db, station_code, scheduled_departure
        )

        features["minutes_since_track_used"] = track_times
        features["minutes_since_platform_used"] = platform_times

        # Enhanced feature extraction logging
        logger.info(
            "features_extracted",
            station_code=station_code,
            train_id=train_id,
            features=features,
        )

        # Log feature validation and quality
        feature_quality_score = self._assess_feature_quality(features)
        logger.info(
            "feature_quality_assessment",
            station_code=station_code,
            train_id=train_id,
            quality_score=feature_quality_score,
            track_usage_data_points=len(track_times),
            platform_usage_data_points=len(platform_times),
            scheduled_departure_hour=features.get("hour_of_day"),
            is_weekend=features.get("day_of_week") in [0, 6],  # Sunday=0, Saturday=6
        )

        return features

    def _assess_feature_quality(self, features: dict[str, Any]) -> float:
        """
        Assess the quality/completeness of extracted features.

        Returns:
            Score from 0.0 to 1.0 indicating feature quality
        """
        quality_score = 0.0
        max_score = 6.0  # Total possible points

        # Basic features (always available) - 2 points
        if features.get("hour_of_day") is not None:
            quality_score += 1.0
        if features.get("day_of_week") is not None:
            quality_score += 1.0

        # Train metadata - 2 points
        if features.get("is_amtrak") is not None:
            quality_score += 0.5
        if features.get("line_code") and features["line_code"] != "UNKNOWN":
            quality_score += 0.5
        if features.get("destination") and features["destination"] != "UNKNOWN":
            quality_score += 1.0

        # Time-based usage data - 2 points
        track_times = features.get("minutes_since_track_used", {})
        platform_times = features.get("minutes_since_platform_used", {})

        if len(track_times) >= 15:  # Good historical track data
            quality_score += 1.0
        elif len(track_times) >= 5:  # Some track data
            quality_score += 0.5

        if len(platform_times) >= 8:  # Good platform usage data
            quality_score += 1.0
        elif len(platform_times) >= 3:  # Some platform data
            quality_score += 0.5

        return round(quality_score / max_score, 2)

    async def _get_minutes_since_track_used(
        self, db: AsyncSession, station_code: str, scheduled_departure: datetime
    ) -> dict[str, float]:
        """
        Calculate minutes since each track was last used.

        Returns dict mapping track -> minutes since last use
        """

        # Query recent track usage (last 24 hours)
        cutoff_time = scheduled_departure - timedelta(hours=24)

        stmt = (
            select(
                JourneyStop.track,
                func.max(JourneyStop.scheduled_departure).label("last_used"),
            )
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    JourneyStop.track.isnot(None),
                    JourneyStop.track != "",
                    JourneyStop.scheduled_departure < scheduled_departure,
                    JourneyStop.scheduled_departure > cutoff_time,
                )
            )
            .group_by(JourneyStop.track)
        )

        result = await db.execute(stmt)
        track_times = {}

        for row in result:
            track = row.track
            last_used = ensure_timezone_aware(row.last_used)
            minutes_since = (scheduled_departure - last_used).total_seconds() / 60
            track_times[track] = minutes_since

        # Log track usage analysis
        logger.info(
            "track_usage_analysis",
            station_code=station_code,
            tracks_found=len(track_times),
            avg_minutes_since_use=(
                round(sum(track_times.values()) / len(track_times), 1)
                if track_times
                else 0
            ),
            most_recent_track=(
                min(track_times.items(), key=lambda x: x[1]) if track_times else None
            ),
            oldest_usage=(
                max(track_times.items(), key=lambda x: x[1]) if track_times else None
            ),
        )

        return track_times

    async def _get_minutes_since_platform_used(
        self, db: AsyncSession, station_code: str, scheduled_departure: datetime
    ) -> dict[str, float]:
        """
        Calculate minutes since each platform was last used.

        Returns dict mapping platform -> minutes since last use
        """

        # For non-NY stations, platforms are same as tracks
        if station_code != "NY":
            return await self._get_minutes_since_track_used(
                db, station_code, scheduled_departure
            )

        # Query recent track usage and group by platform
        cutoff_time = scheduled_departure - timedelta(hours=24)

        stmt = (
            select(JourneyStop.track, JourneyStop.scheduled_departure)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    JourneyStop.track.isnot(None),
                    JourneyStop.track != "",
                    JourneyStop.scheduled_departure < scheduled_departure,
                    JourneyStop.scheduled_departure > cutoff_time,
                )
            )
            .order_by(JourneyStop.scheduled_departure.desc())
        )

        result = await db.execute(stmt)

        # Group by platform and find most recent use
        platform_times = {}

        for row in result:
            track = row.track
            platform = get_platform_for_track(station_code, track)
            departure_time = ensure_timezone_aware(row.scheduled_departure)

            if platform not in platform_times:
                # First (most recent) occurrence of this platform
                minutes_since = (
                    scheduled_departure - departure_time
                ).total_seconds() / 60
                platform_times[platform] = minutes_since

        # Log platform usage analysis
        logger.info(
            "platform_usage_analysis",
            station_code=station_code,
            platforms_found=len(platform_times),
            avg_minutes_since_use=(
                round(sum(platform_times.values()) / len(platform_times), 1)
                if platform_times
                else 0
            ),
            most_recent_platform=(
                min(platform_times.items(), key=lambda x: x[1])
                if platform_times
                else None
            ),
            oldest_platform_usage=(
                max(platform_times.items(), key=lambda x: x[1])
                if platform_times
                else None
            ),
        )

        return platform_times

    async def _get_track_occupancy_flags(
        self, db: AsyncSession, station_code: str, scheduled_departure: datetime
    ) -> dict[str, int]:
        """
        Get binary occupancy flags for each track at the station.

        A track is considered occupied if there's a train scheduled within
        a tight window around our departure time (10 min early + 2 min late).

        Returns dict mapping 'is_track_X_occupied' -> 0 or 1
        """

        # Tight window: 10 minutes early + 2 minutes late
        window_start = scheduled_departure - timedelta(minutes=10)
        window_end = scheduled_departure + timedelta(minutes=2)

        # Find tracks with trains in the occupancy window
        stmt = (
            select(JourneyStop.track)
            .join(TrainJourney)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    JourneyStop.track.isnot(None),
                    JourneyStop.track != "",
                    # Train is scheduled around this time
                    JourneyStop.scheduled_departure >= window_start,
                    JourneyStop.scheduled_departure <= window_end,
                    # Only consider active journeys (not expired/cancelled)
                    TrainJourney.is_expired == False,  # noqa: E712
                    TrainJourney.is_cancelled == False,  # noqa: E712
                )
            )
        )

        result = await db.execute(stmt)
        occupied_tracks = {row.track for row in result}

        # Create binary flags for NY Penn tracks (all possible tracks)
        track_flags = {}
        ny_tracks = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
        ]

        for track in ny_tracks:
            track_flags[f"is_track_{track}_occupied"] = (
                1 if track in occupied_tracks else 0
            )

        # Log occupancy analysis
        occupied_count = sum(track_flags.values())
        logger.info(
            "track_occupancy_analysis",
            station_code=station_code,
            window_start=window_start,
            window_end=window_end,
            occupied_tracks=sorted(occupied_tracks),
            occupied_count=occupied_count,
            total_tracks=len(ny_tracks),
        )

        return track_flags
