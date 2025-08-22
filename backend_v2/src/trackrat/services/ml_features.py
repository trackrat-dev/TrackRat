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
            - day_of_week: 0-6 (0=Sunday)
            - is_amtrak: 0 or 1
            - line_code: String
            - destination: String
            - minutes_since_track_used: Float (-1 if unknown)
            - minutes_since_platform_used: Float (-1 if unknown)
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

        # Calculate time since track was last used
        track_usage_dict = await self._get_minutes_since_track_used(
            db, station_code, scheduled_departure
        )
        features["minutes_since_track_used"] = track_usage_dict

        # Calculate time since platform was last used
        platform_usage_dict = await self._get_minutes_since_platform_used(
            db, station_code, scheduled_departure
        )
        features["minutes_since_platform_used"] = platform_usage_dict

        logger.info(
            "features_extracted",
            station_code=station_code,
            train_id=train_id,
            features=features,
        )

        return features

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

        # Return -1 for tracks not recently used
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

        return platform_times
