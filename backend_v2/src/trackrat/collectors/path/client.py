"""
PATH Transiter API client for TrackRat V2.

Handles communication with the Transiter API for PATH train data.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

import httpx
from pydantic import BaseModel
from structlog import get_logger

from trackrat.collectors.base import BaseClient
from trackrat.utils.metrics import track_api_call

logger = get_logger(__name__)

# Transiter API base URL for PATH
TRANSITER_BASE_URL = "https://demo.transiter.dev/systems/us-ny-path"


class PathStopTime(BaseModel):
    """Represents a scheduled arrival at a PATH station."""

    trip_id: str
    route_id: str
    route_color: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    headsign: str | None = None
    direction_id: bool | None = None
    stop_sequence: int | None = None

    @classmethod
    def from_transiter(cls, data: dict[str, Any]) -> "PathStopTime | None":
        """Parse a stop time from Transiter API response.

        Args:
            data: Raw stop time data from Transiter

        Returns:
            PathStopTime if parseable, None otherwise
        """
        try:
            trip = data.get("trip", {})
            trip_id = trip.get("id")
            route = trip.get("route", {})
            route_id = route.get("id")

            if not trip_id or not route_id:
                return None

            # Parse departure/arrival times (Unix timestamps as strings)
            departure = data.get("departure", {})
            arrival = data.get("arrival", {})

            departure_time = None
            arrival_time = None

            if departure.get("time"):
                departure_time = datetime.fromtimestamp(int(departure["time"]))
            if arrival.get("time"):
                arrival_time = datetime.fromtimestamp(int(arrival["time"]))

            # Get headsign - prefer trip destination over stop-level headsign
            # The stop-level headsign often shows the current stop, not final destination
            headsign = None
            trip_dest = trip.get("destination", {})
            if trip_dest:
                headsign = trip_dest.get("name")
            if not headsign:
                # Try root-level destination
                dest = data.get("destination", {})
                headsign = dest.get("name") if dest else None
            if not headsign:
                # Last resort: use headsign field
                headsign = data.get("headsign")

            return cls(
                trip_id=trip_id,
                route_id=route_id,
                route_color=route.get("color"),
                departure_time=departure_time,
                arrival_time=arrival_time,
                headsign=headsign,
                direction_id=trip.get("directionId"),
                stop_sequence=data.get("stopSequence"),
            )
        except Exception as e:
            logger.warning("failed_to_parse_path_stop_time", error=str(e), data=data)
            return None


class PathClient(BaseClient):
    """Client for interacting with the Transiter API for PATH data."""

    def __init__(self, timeout: float = 30.0):
        """Initialize the PATH client.

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = TRANSITER_BASE_URL
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

        # Simple in-memory cache for station arrivals
        self._cache: dict[str, list[PathStopTime]] = {}
        self._cache_time: dict[str, datetime] = {}
        self._cache_ttl = 30  # 30 second cache TTL

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create the HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": "TrackRat-V2/1.0",
                    "Accept": "application/json",
                },
            )
        return self._session

    async def __aenter__(self) -> "Self":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None

    async def get_train_data(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, list[PathStopTime]]:
        """Get all train data - satisfies BaseClient interface.

        Returns:
            Dictionary mapping station IDs to lists of stop times
        """
        # This is a placeholder - actual discovery uses get_station_arrivals
        return self._cache

    @track_api_call(api_name="path", endpoint="station_arrivals")
    async def get_station_arrivals(
        self, transiter_stop_id: str
    ) -> list[PathStopTime]:
        """Fetch upcoming arrivals at a PATH station.

        Args:
            transiter_stop_id: Transiter stop ID (e.g., '26735' for Hoboken)

        Returns:
            List of upcoming arrivals at this station
        """
        # Check cache first
        if self._is_cache_valid(transiter_stop_id):
            logger.debug("returning_cached_path_arrivals", stop_id=transiter_stop_id)
            return self._cache.get(transiter_stop_id, [])

        url = f"{self.base_url}/stops/{transiter_stop_id}"

        try:
            logger.debug("fetching_path_arrivals", stop_id=transiter_stop_id, url=url)

            response = await self.session.get(url)
            response.raise_for_status()

            data = response.json()

            # Parse stop times from response
            stop_times = []
            for st_data in data.get("stopTimes", []):
                stop_time = PathStopTime.from_transiter(st_data)
                if stop_time:
                    stop_times.append(stop_time)

            # Update cache
            self._cache[transiter_stop_id] = stop_times
            self._cache_time[transiter_stop_id] = datetime.now()

            logger.debug(
                "path_arrivals_fetched",
                stop_id=transiter_stop_id,
                arrival_count=len(stop_times),
            )

            return stop_times

        except httpx.HTTPStatusError as e:
            logger.error(
                "path_api_http_error",
                stop_id=transiter_stop_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "path_api_failed",
                stop_id=transiter_stop_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    def _is_cache_valid(self, stop_id: str) -> bool:
        """Check if the cache is still valid for a station.

        Args:
            stop_id: Station ID to check

        Returns:
            True if cache exists and is not expired
        """
        if stop_id not in self._cache or stop_id not in self._cache_time:
            return False

        age = datetime.now() - self._cache_time[stop_id]
        return age < timedelta(seconds=self._cache_ttl)

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
        self._cache_time.clear()
        logger.debug("path_cache_cleared")
