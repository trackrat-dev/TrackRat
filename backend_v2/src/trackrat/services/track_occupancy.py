"""
Track occupancy service for determining occupied tracks at stations.
"""

import asyncio
from datetime import timedelta

from cachetools import TTLCache
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import OccupiedTracksResponse
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.settings import get_settings
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# A track counts as occupied when a not-yet-departed train's effective
# departure (or arrival, for trains terminating at this station) falls within
# this window around now. The future bound covers the boarding window during
# which equipment is already sitting on the track before its departure time;
# the past bound covers delayed trains whose scheduled time has slipped past
# and terminating trains dwelling on the track after arrival, while keeping
# stale/abandoned rows from pinning a track "occupied" indefinitely.
# (Issue #1676: the previous "scheduled_departure within the next 2 hours"
# window both over-included far-future reservations and missed delayed and
# terminating trains entirely.)
OCCUPIED_WINDOW_PAST_MINUTES = 20
OCCUPIED_WINDOW_FUTURE_MINUTES = 20


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
        """Get tracks with a train at (or imminently at) the platform now."""
        now = now_et()
        window_start = now - timedelta(minutes=OCCUPIED_WINDOW_PAST_MINUTES)
        window_end = now + timedelta(minutes=OCCUPIED_WINDOW_FUTURE_MINUTES)

        # Live departure estimate, correcting the NJT TIME/DEP_TIME inversion
        # via the documented SQL twin of utils/train.effective_njt_updated_times:
        # GREATEST(updated_departure, updated_arrival) guarded to NJT rows with
        # both fields present (see JourneyStop model docs / journey-lifecycle.md
        # §2). At an NJT terminal the GREATEST yields the turnaround departure
        # when present — which is genuinely when the track frees up, so no
        # terminal exemption is needed for occupancy.
        live_departure = case(
            (
                and_(
                    TrainJourney.data_source == "NJT",
                    JourneyStop.updated_departure.is_not(None),
                    JourneyStop.updated_arrival.is_not(None),
                ),
                func.greatest(
                    JourneyStop.updated_departure, JourneyStop.updated_arrival
                ),
            ),
            else_=JourneyStop.updated_departure,
        )

        # When the train is expected to leave the track: live then scheduled
        # departure; for trains terminating here (no departure at all), the
        # arrival — the past window then grants them dwell time on the track.
        occupies_until = func.coalesce(
            live_departure,
            JourneyStop.scheduled_departure,
            JourneyStop.updated_arrival,
            JourneyStop.scheduled_arrival,
        )

        stmt = (
            select(JourneyStop.track)
            .join(TrainJourney)
            .where(
                and_(
                    JourneyStop.station_code.in_(expand_station_codes(station_code)),
                    JourneyStop.track.is_not(None),
                    JourneyStop.has_departed_station.is_not(True),
                    occupies_until >= window_start,
                    occupies_until <= window_end,
                    TrainJourney.is_cancelled.is_not(True),
                )
            )
            .distinct()
        )

        result = await session.execute(stmt)
        tracks = result.scalars().all()

        # Filter out None values and convert to set
        return {str(track) for track in tracks if track is not None}


# Lazy singleton instance
_track_occupancy_service: TrackOccupancyService | None = None


def get_track_occupancy_service() -> TrackOccupancyService:
    global _track_occupancy_service
    if _track_occupancy_service is None:
        _track_occupancy_service = TrackOccupancyService()
    return _track_occupancy_service
