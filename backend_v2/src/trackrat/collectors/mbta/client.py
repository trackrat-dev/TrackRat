"""
MBTA GTFS-RT client for fetching real-time Commuter Rail data.

Uses MBTA's CDN-hosted GTFS-RT protobuf feed (no auth required).
Only processes Commuter Rail trips (route_id starting with "CR-" or "CapeFlyer").
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.config.stations import (
    MBTA_GTFS_RT_FEED_URL,
    MBTA_GTFS_STOP_TO_INTERNAL_MAP,
    MBTA_ROUTES,
)

logger = logging.getLogger(__name__)


class MbtaArrival(BaseModel):
    """A single arrival/stop time from the MBTA GTFS-RT feed."""

    station_code: str  # Our internal station code
    gtfs_stop_id: str  # Original GTFS stop_id
    trip_id: str
    route_id: str
    direction_id: int  # 0 = outbound from Boston, 1 = inbound to Boston
    headsign: str | None
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None  # Not available in protobuf; supplemented via V3 API

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class MBTAClient:
    """
    Client for fetching MBTA Commuter Rail real-time data from GTFS-RT feed.

    The MBTA GTFS-RT feed contains ALL modes (bus, subway, CR, ferry).
    This client filters to Commuter Rail trips only (route_id starting with
    "CR-" or "CapeFlyer").

    Unlike MTA feeds, MBTA does NOT use custom protobuf extensions for track
    assignments. Track data is available via the V3 JSON API but is not
    fetched here (can be supplemented separately if needed).
    """

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize MBTA client.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._cache: list[MbtaArrival] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # seconds

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (MBTA Real-time Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "MBTAClient":
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
        return MBTA_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    def _get_route_info(self, route_id: str) -> tuple[str, str, str] | None:
        """Get route info (line_code, name, color) for a route ID."""
        return MBTA_ROUTES.get(route_id)

    @staticmethod
    def _is_commuter_rail(route_id: str) -> bool:
        """Check if a route ID is a Commuter Rail route."""
        return route_id.startswith("CR-") or route_id == "CapeFlyer"

    async def get_all_arrivals(self) -> list[MbtaArrival]:
        """
        Fetch and parse all MBTA Commuter Rail arrivals from GTFS-RT feed.

        The feed contains all modes; we filter to CR routes only.
        Returns cached data if still valid (within TTL).

        Returns:
            List of MbtaArrival objects for all upcoming CR stops
        """
        if self._is_cache_valid():
            return self._cache or []

        try:
            response = await self.session.get(MBTA_GTFS_RT_FEED_URL)
            response.raise_for_status()

            # Parse protobuf
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            arrivals: list[MbtaArrival] = []

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                trip_update = entity.trip_update
                trip = trip_update.trip

                trip_id = trip.trip_id if trip.HasField("trip_id") else ""
                route_id = trip.route_id if trip.HasField("route_id") else ""
                direction_id = trip.direction_id if trip.HasField("direction_id") else 0

                # Filter to Commuter Rail only
                if not self._is_commuter_rail(route_id):
                    continue

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

                    # GTFS-RT origins may only have departure (no arrival).
                    if arrival_time is None:
                        if departure_time is None:
                            continue
                        arrival_time = departure_time

                    # MBTA does not use MTA protobuf extensions for track;
                    # track data would come from V3 API if needed.
                    arrivals.append(
                        MbtaArrival(
                            station_code=station_code,
                            gtfs_stop_id=gtfs_stop_id,
                            trip_id=trip_id,
                            route_id=route_id,
                            direction_id=direction_id,
                            headsign=headsign,
                            arrival_time=arrival_time,
                            departure_time=departure_time,
                            delay_seconds=delay_seconds,
                            track=None,
                        )
                    )

            # Cache results
            self._cache = arrivals
            self._cache_time = datetime.now(UTC)

            logger.info(f"Fetched {len(arrivals)} MBTA CR arrivals from GTFS-RT feed")
            return arrivals

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching MBTA GTFS-RT feed: {e}")
            return self._cache or []
        except Exception as e:
            logger.error(f"Error parsing MBTA GTFS-RT feed: {e}")
            return self._cache or []

    async def get_station_arrivals(self, station_code: str) -> list[MbtaArrival]:
        """Get arrivals for a specific station."""
        all_arrivals = await self.get_all_arrivals()
        return [a for a in all_arrivals if a.station_code == station_code]

    async def get_trip_stops(self, trip_id: str) -> list[MbtaArrival]:
        """Get all stops for a specific trip, sorted by arrival time."""
        all_arrivals = await self.get_all_arrivals()
        trip_stops = [a for a in all_arrivals if a.trip_id == trip_id]
        return sorted(trip_stops, key=lambda a: a.arrival_time)

    def clear_cache(self) -> None:
        """Clear the cached data."""
        self._cache = None
        self._cache_time = None
