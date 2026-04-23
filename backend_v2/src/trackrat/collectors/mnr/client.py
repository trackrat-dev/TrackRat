"""
Metro-North GTFS-RT client for fetching real-time train data.

Uses MTA's official GTFS-RT feed directly with gtfs-realtime-bindings for parsing.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.collectors.mta_extensions import extract_mta_track
from trackrat.config.stations import (
    MNR_GTFS_RT_FEED_URL,
    MNR_GTFS_STOP_TO_INTERNAL_MAP,
    MNR_ROUTES,
)

logger = logging.getLogger(__name__)

# Phase-broken HTTP timeout. Bounds a hung TCP connect or stalled TLS handshake
# independently from read time so an unreachable MTA host can't consume the
# scheduler's 480s budget waiting on a scalar read timeout.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


class MnrArrival(BaseModel):
    """A single arrival/stop time from the Metro-North GTFS-RT feed."""

    station_code: str  # Our internal station code
    gtfs_stop_id: str  # Original GTFS stop_id
    trip_id: str
    route_id: str
    direction_id: int  # 0 = outbound from GCT, 1 = inbound to GCT
    headsign: str | None
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None  # Track assignment if available via MTA extension

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class MNRClient:
    """
    Client for fetching Metro-North real-time data from MTA GTFS-RT feed.

    Parses GTFS-RT protobuf format and converts to our internal models.
    Uses a 30-second cache to minimize API calls.
    """

    def __init__(
        self, timeout: httpx.Timeout | float | None = None
    ) -> None:
        """Initialize Metro-North client.

        Args:
            timeout: httpx.Timeout instance or scalar seconds. Defaults to a
                phase-broken timeout (connect=5s, read=15s, write=5s, pool=5s)
                so a hung TCP connect can't hold the whole collector.
        """
        self.timeout: httpx.Timeout | float = (
            timeout if timeout is not None else _DEFAULT_TIMEOUT
        )
        self._session: httpx.AsyncClient | None = None
        self._cache: list[MnrArrival] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # seconds

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (Metro-North Real-time Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "MNRClient":
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
        return MNR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    def _get_route_info(self, route_id: str) -> tuple[str, str, str] | None:
        """Get route info (line_code, name, color) for a route ID."""
        return MNR_ROUTES.get(route_id)

    async def get_all_arrivals(self) -> list[MnrArrival]:
        """
        Fetch and parse all Metro-North arrivals from GTFS-RT feed.

        Returns cached data if still valid (within TTL).

        Returns:
            List of MnrArrival objects for all upcoming stops
        """
        if self._is_cache_valid():
            return self._cache or []

        try:
            response = await self.session.get(MNR_GTFS_RT_FEED_URL)
            response.raise_for_status()

            # Parse protobuf
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            arrivals: list[MnrArrival] = []

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                trip_update = entity.trip_update
                trip = trip_update.trip

                trip_id = trip.trip_id if trip.HasField("trip_id") else ""
                route_id = trip.route_id if trip.HasField("route_id") else ""
                direction_id = trip.direction_id if trip.HasField("direction_id") else 0

                # Try to get headsign from trip descriptor extension or leave as None
                headsign: str | None = None

                for stu in trip_update.stop_time_update:
                    gtfs_stop_id = stu.stop_id if stu.HasField("stop_id") else ""
                    station_code = self._map_stop_id(gtfs_stop_id)

                    if not station_code:
                        # Skip stops we don't have mapped
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
                    # Use departure_time as fallback to keep the stop.
                    if arrival_time is None:
                        if departure_time is None:
                            continue
                        arrival_time = departure_time

                    # Extract track from MTA Railroad GTFS-RT extension (field 1005)
                    track = extract_mta_track(stu)

                    arrivals.append(
                        MnrArrival(
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

            logger.info(f"Fetched {len(arrivals)} MNR arrivals from GTFS-RT feed")
            return arrivals

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching MNR GTFS-RT feed: {e}")
            # Return cached data if available, even if stale
            return self._cache or []
        except Exception as e:
            logger.error(f"Error parsing MNR GTFS-RT feed: {e}")
            return self._cache or []

    async def get_station_arrivals(self, station_code: str) -> list[MnrArrival]:
        """
        Get arrivals for a specific station.

        Args:
            station_code: Our internal station code (e.g., 'GCT' for Grand Central)

        Returns:
            List of arrivals at the specified station
        """
        all_arrivals = await self.get_all_arrivals()
        return [a for a in all_arrivals if a.station_code == station_code]

    async def get_trip_stops(self, trip_id: str) -> list[MnrArrival]:
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
