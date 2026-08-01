"""
Track occupancy service for determining occupied tracks at stations.
"""

import asyncio
from datetime import timedelta

from cachetools import TTLCache
from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import OccupiedTracksResponse
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.settings import get_settings
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# A track counts as occupied when a train is at (or imminently at) the
# platform now. Two cases:
#
# - Departing/through trains: a not-yet-departed train whose effective
#   departure falls within [now - PAST, now + FUTURE]. The future bound
#   covers the boarding window during which equipment is already sitting on
#   the track before its departure time; the past bound covers delayed
#   trains whose scheduled time has slipped past, while keeping
#   stale/abandoned rows from pinning a track "occupied" indefinitely.
# - Terminating trains: occupied from (effective) arrival until the PAST
#   window elapses (dwell before the equipment moves to the yard). A future
#   arrival is a reservation, not occupancy, so it does not get the FUTURE
#   bound.
#
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

        # Terminal stops are occupancy-relevant on arrival, not departure:
        # the shared MTA collectors flag has_departed_station as soon as a
        # train arrives at its terminal (mta_common.update_stop_departure_status
        # paths A/B), so that flag cannot gate terminal dwell, and a terminal
        # row's departure fields don't describe when its track frees.
        #
        # Guarded against placeholder journeys for the same reason as
        # utils/train.terminal_stop_index: NJT discovery/schedule create
        # single-stop journeys whose terminal_station_code (and origin) is the
        # board station until full collection rewrites it — and that stop is
        # exactly the one carrying a track. Bare equality would route it to
        # the arrival branch, reading the track as free while the train
        # boards and as occupied for a dwell window after it departs. No real
        # journey has origin == terminal, so the inequality confines the
        # arrival branch to genuine terminals; placeholder rows take the
        # (has_departed_station-gated) departure branch instead.
        is_terminal_stop = and_(
            JourneyStop.station_code == TrainJourney.terminal_station_code,
            TrainJourney.origin_station_code != TrainJourney.terminal_station_code,
        )

        # Live departure estimate, correcting the NJT TIME/DEP_TIME inversion
        # via the documented SQL twin of utils/train.effective_njt_updated_times:
        # GREATEST(updated_departure, updated_arrival) guarded to NJT rows with
        # both fields present (see JourneyStop model docs / journey-lifecycle.md
        # §2). Never applied at the terminal — terminal stops take the arrival
        # branch below, preserving the #1492 exemption.
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
        departure_time = func.coalesce(live_departure, JourneyStop.scheduled_departure)

        # Departing/through trains: not yet departed, effective departure
        # within the boarding/delay window.
        departure_branch = and_(
            not_(is_terminal_stop),
            JourneyStop.has_departed_station.is_not(True),
            departure_time >= window_start,
            departure_time <= window_end,
        )

        # Terminating trains: occupied from (effective) arrival until the
        # dwell window elapses. A future arrival is a reservation, not
        # occupancy, so the upper bound is now — not the boarding window.
        arrival_time = func.coalesce(
            JourneyStop.actual_arrival,
            JourneyStop.updated_arrival,
            JourneyStop.scheduled_arrival,
        )
        terminal_branch = and_(
            is_terminal_stop,
            arrival_time >= window_start,
            arrival_time <= now,
        )

        stmt = (
            select(JourneyStop.track)
            .join(TrainJourney)
            .where(
                and_(
                    JourneyStop.station_code.in_(expand_station_codes(station_code)),
                    JourneyStop.track.is_not(None),
                    # Sargable pre-filters, deliberately wider than the exact
                    # branch windows below: without them the computed
                    # COALESCE/CASE expressions would force Postgres to scan
                    # the station's full retention window and filter by hand —
                    # the #1354 class of multi-minute scan. journey_date prunes
                    # partitions (any train on a track now began its journey
                    # within the last 2 days, including overnight runs). The
                    # scheduled_departure disjunction: an occupying row's
                    # scheduled departure is near now (a delay beyond 24h is
                    # stale data; +1h absorbs early terminal arrivals whose
                    # GTFS scheduled departure equals their arrival), absent
                    # entirely (terminating trains without one), or — the
                    # terminal-row exemption — an NJT turnaround DEP_TIME that
                    # journey collection persisted into scheduled_departure
                    # (the #1492 family), which can sit hours in the future
                    # while the train dwells; without the exemption a >1h
                    # layover would hide the occupied track. The two
                    # time-based arms keep idx_station_times fully usable on
                    # their own; the join-dependent terminal arm degrades the
                    # worst case to a station_code-prefix scan over the
                    # partition-pruned rows — still station-bounded, unlike
                    # #1354.
                    JourneyStop.journey_date >= now.date() - timedelta(days=2),
                    or_(
                        and_(
                            JourneyStop.scheduled_departure
                            >= now - timedelta(hours=24),
                            JourneyStop.scheduled_departure <= now + timedelta(hours=1),
                        ),
                        JourneyStop.scheduled_departure.is_(None),
                        is_terminal_stop,
                    ),
                    TrainJourney.is_cancelled.is_not(True),
                    or_(departure_branch, terminal_branch),
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
