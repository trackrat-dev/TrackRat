"""
Track occupancy service for determining occupied tracks at stations.
"""

import asyncio
from datetime import timedelta

from cachetools import TTLCache
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import OccupiedTracksResponse
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.settings import get_settings
from trackrat.utils.time import now_et

logger = get_logger(__name__)


class TrackOccupancyService:
    """Service for determining occupied tracks at stations with caching."""

    def __init__(self) -> None:
        """Initialize track occupancy service."""
        self.settings = get_settings()
        # Simple in-memory cache with 1-minute TTL
        self._cache: TTLCache[str, OccupiedTracksResponse] = TTLCache(
            maxsize=100, ttl=60
        )
        self._fetch_lock = asyncio.Lock()

    async def get_occupied_tracks(self, station_code: str) -> OccupiedTracksResponse:
        """Get occupied tracks with JIT caching."""
        cache_key = f"occupied_tracks:{station_code}"

        # Check cache first
        cached_result: OccupiedTracksResponse | None = self._cache.get(cache_key)
        if cached_result:
            logger.debug("occupied_tracks_cache_hit", station_code=station_code)
            return cached_result

        # Use lock to prevent multiple simultaneous fetches
        async with self._fetch_lock:
            # Double-check cache after acquiring lock
            cached_result = self._cache.get(cache_key)
            if cached_result:
                logger.debug(
                    "occupied_tracks_cache_hit_after_lock", station_code=station_code
                )
                return cached_result

            logger.info("occupied_tracks_cache_miss", station_code=station_code)

            # Fetch fresh data
            occupied_tracks = await self._fetch_occupied_tracks(station_code)

            # Create response
            now = now_et()
            response = OccupiedTracksResponse(
                station_code=station_code,
                station_name=get_station_name(station_code),
                occupied_tracks=list(occupied_tracks),
                last_updated=now,
                cache_expires_at=now + timedelta(minutes=1),
            )

            # Cache the response
            self._cache[cache_key] = response

            logger.info(
                "occupied_tracks_fetched",
                station_code=station_code,
                track_count=len(occupied_tracks),
                tracks=list(occupied_tracks),
            )

            return response

    async def _fetch_occupied_tracks(self, station_code: str) -> set[str]:
        """Fetch occupied tracks from database."""
        try:
            async with get_session() as session:
                occupied_tracks = await self._get_database_tracks(station_code, session)

                logger.debug(
                    "occupied_tracks_query_completed",
                    station_code=station_code,
                    track_count=len(occupied_tracks),
                )

                return occupied_tracks
        except Exception as e:
            logger.error(
                "occupied_tracks_fetch_failed",
                station_code=station_code,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Return empty set on error
            return set()

    async def _get_database_tracks(
        self, station_code: str, session: AsyncSession
    ) -> set[str]:
        """Get tracks from trains in database that haven't departed yet."""
        # Look for trains departing within the next 2 hours
        cutoff_time = now_et() + timedelta(hours=2)
        current_time = now_et()

        stmt = (
            select(JourneyStop.track)
            .join(TrainJourney)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    JourneyStop.track.is_not(None),
                    JourneyStop.has_departed_station.is_not(True),
                    JourneyStop.scheduled_departure >= current_time,
                    JourneyStop.scheduled_departure <= cutoff_time,
                    TrainJourney.is_cancelled.is_not(True),
                )
            )
            .distinct()
        )

        result = await session.execute(stmt)
        tracks = result.scalars().all()

        # Filter out None values and convert to set
        return {str(track) for track in tracks if track is not None}


# Singleton instance
track_occupancy_service = TrackOccupancyService()
