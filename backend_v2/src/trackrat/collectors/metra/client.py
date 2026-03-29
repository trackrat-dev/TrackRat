"""
Metra GTFS-RT client for fetching real-time train data.

Uses Metra's official GTFS-RT feed with API token authentication.
Follows the same pattern as the LIRR client.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.config.stations.metra import (
    METRA_GTFS_RT_FEED_URL,
    METRA_GTFS_STOP_TO_INTERNAL_MAP,
    METRA_ROUTES,
)

logger = logging.getLogger(__name__)


class MetraArrival(BaseModel):
    """A single arrival/stop time from the Metra GTFS-RT feed."""

    station_code: str  # Our internal station code (same as GTFS stop_id for Metra)
    gtfs_stop_id: str  # Original GTFS stop_id
    trip_id: str
    route_id: str
    direction_id: int  # 0 = outbound from Chicago, 1 = inbound to Chicago
    headsign: str | None
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None  # Metra does not publish track in GTFS-RT

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class MetraClient:
    """
    Client for fetching Metra real-time data from GTFS-RT feed.

    Parses GTFS-RT protobuf format and converts to our internal models.
    Uses a 30-second cache to minimize API calls.
    Requires TRACKRAT_METRA_API_TOKEN environment variable.
    """

    def __init__(self, api_token: str | None = None, timeout: float = 30.0) -> None:
        """Initialize Metra client.

        Args:
            api_token: Metra API token. If None, reads from settings.
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        if api_token is None:
            from trackrat.settings import get_settings

            api_token = get_settings().metra_api_token
        self._api_token = api_token
        self._session: httpx.AsyncClient | None = None
        self._cache: list[MetraArrival] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # seconds

        if not self._api_token:
            logger.warning(
                "TRACKRAT_METRA_API_TOKEN not set — Metra collection will be skipped"
            )

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (Metra Real-time Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "MetraClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._cache is None or self._cache_time is None:
            return False
        age = (datetime.now(UTC) - self._cache_time).total_seconds()
        return age < self._cache_ttl

    def _map_stop_id(self, gtfs_stop_id: str) -> str | None:
        """Map GTFS stop_id to our internal station code."""
        return METRA_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    def _get_route_info(self, route_id: str) -> tuple[str, str, str] | None:
        """Get route info (line_code, name, color) for a route ID."""
        return METRA_ROUTES.get(route_id)

    async def get_all_arrivals(self) -> list[MetraArrival]:
        """
        Fetch and parse all Metra arrivals from GTFS-RT feed.

        Returns cached data if still valid (within TTL).

        Returns:
            List of MetraArrival objects for all upcoming stops.
            Empty list if API token is not configured.
        """
        if not self._api_token:
            return []

        if self._is_cache_valid():
            return self._cache or []

        try:
            url = f"{METRA_GTFS_RT_FEED_URL}?api_token={self._api_token}"
            response = await self.session.get(url)
            response.raise_for_status()

            # Parse protobuf
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            arrivals: list[MetraArrival] = []

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                trip_update = entity.trip_update
                trip = trip_update.trip

                trip_id = trip.trip_id if trip.HasField("trip_id") else ""
                route_id = trip.route_id if trip.HasField("route_id") else ""
                direction_id = trip.direction_id if trip.HasField("direction_id") else 0

                headsign: str | None = None

                for stu in trip_update.stop_time_update:
                    gtfs_stop_id = stu.stop_id if stu.HasField("stop_id") else ""
                    station_code = self._map_stop_id(gtfs_stop_id)

                    if not station_code:
                        continue

                    # Parse arrival time
                    arrival_time: datetime | None = None
                    delay_seconds = 0
                    if stu.HasField("arrival"):
                        arr = stu.arrival
                        if arr.HasField("time"):
                            arrival_time = datetime.fromtimestamp(arr.time, tz=UTC)
                        if arr.HasField("delay"):
                            delay_seconds = arr.delay

                    # Parse departure time
                    departure_time: datetime | None = None
                    if stu.HasField("departure"):
                        dep = stu.departure
                        if dep.HasField("time"):
                            departure_time = datetime.fromtimestamp(dep.time, tz=UTC)

                    # Origin stops may only have departure (no arrival).
                    if arrival_time is None:
                        if departure_time is None:
                            continue
                        arrival_time = departure_time

                    # Metra GTFS-RT does not include track assignments
                    track = None

                    arrivals.append(
                        MetraArrival(
                            station_code=station_code,
                            gtfs_stop_id=gtfs_stop_id,
                            trip_id=trip_id,
                            route_id=route_id,
                            direction_id=direction_id,
                            headsign=headsign,
                            arrival_time=arrival_time,
                            departure_time=departure_time,
                            delay_seconds=delay_seconds,
                            track=track,
                        )
                    )

            # Cache results
            self._cache = arrivals
            self._cache_time = datetime.now(UTC)

            logger.info(f"Fetched {len(arrivals)} Metra arrivals from GTFS-RT feed")
            return arrivals

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Metra GTFS-RT feed: {e.response.status_code}")
            return self._cache or []
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Metra GTFS-RT feed: {type(e).__name__}")
            return self._cache or []
        except Exception as e:
            logger.error(f"Error parsing Metra GTFS-RT feed: {e}")
            return self._cache or []

    async def get_station_arrivals(self, station_code: str) -> list[MetraArrival]:
        """
        Get arrivals for a specific station.

        Args:
            station_code: Our internal station code (e.g., 'CUS')

        Returns:
            List of arrivals at the specified station
        """
        all_arrivals = await self.get_all_arrivals()
        return [a for a in all_arrivals if a.station_code == station_code]

    async def get_trip_stops(self, trip_id: str) -> list[MetraArrival]:
        """
        Get all stops for a specific trip.

        Args:
            trip_id: GTFS trip_id

        Returns:
            List of stops for the trip, sorted by arrival time
        """
        all_arrivals = await self.get_all_arrivals()
        trip_stops = [a for a in all_arrivals if a.trip_id == trip_id]
        return sorted(trip_stops, key=lambda a: a.arrival_time)

    def clear_cache(self) -> None:
        """Clear the cached data."""
        self._cache = None
        self._cache_time = None
