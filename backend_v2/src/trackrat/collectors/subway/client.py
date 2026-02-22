"""
NYC Subway GTFS-RT client for fetching real-time train data.

Fetches all 8 subway GTFS-RT feeds concurrently and parses them with
the NYCT protobuf extensions for train_id, is_assigned, and direction.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.collectors.mta_extensions import (
    extract_nyct_stop_time_update,
    extract_nyct_trip_descriptor,
)
from trackrat.config.stations import (
    SUBWAY_GTFS_RT_FEED_URLS,
    map_subway_gtfs_stop,
)

logger = logging.getLogger(__name__)

# Maps each GTFS route_id to its feed group key in SUBWAY_GTFS_RT_FEED_URLS
_ROUTE_TO_FEED: dict[str, str] = {
    "1": "1234567S",
    "2": "1234567S",
    "3": "1234567S",
    "4": "1234567S",
    "5": "1234567S",
    "6": "1234567S",
    "6X": "1234567S",
    "7": "1234567S",
    "7X": "1234567S",
    "GS": "1234567S",
    "FS": "1234567S",
    "H": "1234567S",
    "A": "ACE",
    "C": "ACE",
    "E": "ACE",
    "B": "BDFM",
    "D": "BDFM",
    "F": "BDFM",
    "FX": "BDFM",
    "M": "BDFM",
    "G": "G",
    "J": "JZ",
    "Z": "JZ",
    "L": "L",
    "N": "NQRW",
    "Q": "NQRW",
    "R": "NQRW",
    "W": "NQRW",
    "SI": "SIR",
}


class SubwayArrival(BaseModel):
    """A single arrival/stop time from the NYC Subway GTFS-RT feed."""

    station_code: str  # Our internal station code (S-prefixed)
    gtfs_stop_id: str  # Original GTFS stop_id (with N/S suffix)
    trip_id: str
    route_id: str
    direction_id: int  # 0 or 1, mapped from NYCT direction enum
    headsign: str | None
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None  # From NYCT StopTimeUpdate extension
    nyct_train_id: str | None  # From NYCT TripDescriptor extension
    is_assigned: bool  # Whether a physical train is assigned

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


def _nyct_direction_to_direction_id(nyct_direction: int | None) -> int:
    """Convert NYCT direction enum to standard direction_id.

    NYCT: NORTH=1, EAST=2, SOUTH=3, WEST=4
    Standard: 0=one direction (south/west), 1=other direction (north/east)
    """
    if nyct_direction is None:
        return 0
    # NORTH(1) and EAST(2) → direction_id 0 (uptown/east)
    # SOUTH(3) and WEST(4) → direction_id 1 (downtown/west)
    if nyct_direction in (1, 2):
        return 0
    return 1


class SubwayClient:
    """
    Client for fetching NYC Subway real-time data from MTA GTFS-RT feeds.

    Fetches all 8 feed groups concurrently, parses GTFS-RT protobuf format
    with NYCT extensions, and converts to internal models.
    Uses a 30-second per-feed cache to minimize API calls.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._cache: dict[str, list[SubwayArrival]] = {}
        self._cache_times: dict[str, datetime] = {}
        self._cache_ttl = 30  # seconds

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (NYC Subway Real-time Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "SubwayClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _is_feed_cache_valid(self, feed_key: str) -> bool:
        """Check if cached data for a specific feed is still valid."""
        if feed_key not in self._cache or feed_key not in self._cache_times:
            return False
        age = (datetime.now(UTC) - self._cache_times[feed_key]).total_seconds()
        return age < self._cache_ttl

    async def _fetch_feed(self, feed_key: str, feed_url: str) -> list[SubwayArrival]:
        """Fetch and parse a single GTFS-RT feed.

        Args:
            feed_key: Feed group identifier (e.g., "ACE", "BDFM")
            feed_url: URL to fetch

        Returns:
            List of SubwayArrival objects from this feed
        """
        if self._is_feed_cache_valid(feed_key):
            return self._cache[feed_key]

        try:
            response = await self.session.get(feed_url)
            response.raise_for_status()

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            arrivals: list[SubwayArrival] = []

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                trip_update = entity.trip_update
                trip = trip_update.trip

                trip_id = trip.trip_id if trip.HasField("trip_id") else ""
                route_id = trip.route_id if trip.HasField("route_id") else ""

                # Extract NYCT trip descriptor extension
                nyct_desc = extract_nyct_trip_descriptor(trip_update)
                nyct_train_id = nyct_desc["train_id"] if nyct_desc else None
                is_assigned = nyct_desc["is_assigned"] if nyct_desc else False
                nyct_direction = nyct_desc["direction"] if nyct_desc else None
                direction_id = _nyct_direction_to_direction_id(nyct_direction)

                headsign: str | None = None

                for stu in trip_update.stop_time_update:
                    gtfs_stop_id = stu.stop_id if stu.HasField("stop_id") else ""
                    station_code = map_subway_gtfs_stop(gtfs_stop_id)

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

                    # Use departure as fallback for origin stops
                    if arrival_time is None:
                        if departure_time is None:
                            continue
                        arrival_time = departure_time

                    # Extract track from NYCT StopTimeUpdate extension
                    track: str | None = None
                    nyct_stu = extract_nyct_stop_time_update(stu)
                    if nyct_stu:
                        track = nyct_stu["actual_track"] or nyct_stu["scheduled_track"]

                    arrivals.append(
                        SubwayArrival(
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
                            nyct_train_id=nyct_train_id,
                            is_assigned=is_assigned,
                        )
                    )

            # Cache results
            self._cache[feed_key] = arrivals
            self._cache_times[feed_key] = datetime.now(UTC)

            logger.debug(
                f"Fetched {len(arrivals)} subway arrivals from {feed_key} feed"
            )
            return arrivals

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching subway {feed_key} feed: {e}")
            return self._cache.get(feed_key, [])
        except Exception as e:
            logger.error(f"Error parsing subway {feed_key} feed: {e}")
            return self._cache.get(feed_key, [])

    async def get_all_arrivals(self) -> list[SubwayArrival]:
        """
        Fetch and parse all subway arrivals from all 8 GTFS-RT feeds concurrently.

        Returns:
            List of SubwayArrival objects from all feeds, sorted by arrival time
        """
        tasks = [
            self._fetch_feed(key, url) for key, url in SUBWAY_GTFS_RT_FEED_URLS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_arrivals: list[SubwayArrival] = []
        for i, result in enumerate(results):
            feed_key = list(SUBWAY_GTFS_RT_FEED_URLS.keys())[i]
            if isinstance(result, BaseException):
                logger.error(f"Failed to fetch subway {feed_key} feed: {result}")
                all_arrivals.extend(self._cache.get(feed_key, []))
            else:
                all_arrivals.extend(result)

        logger.info(
            f"Fetched {len(all_arrivals)} total subway arrivals from {len(SUBWAY_GTFS_RT_FEED_URLS)} feeds"
        )
        return sorted(all_arrivals, key=lambda a: a.arrival_time)

    async def get_feed_arrivals(self, route_id: str) -> list[SubwayArrival]:
        """Fetch arrivals from a single feed based on route_id.

        Useful for JIT updates where we know the route and only need one feed.
        Falls back to get_all_arrivals if the route_id is unknown.
        """
        feed_key = _ROUTE_TO_FEED.get(route_id)
        if feed_key and feed_key in SUBWAY_GTFS_RT_FEED_URLS:
            return await self._fetch_feed(feed_key, SUBWAY_GTFS_RT_FEED_URLS[feed_key])
        # Unknown route — fall back to all feeds
        return await self.get_all_arrivals()

    async def get_station_arrivals(self, station_code: str) -> list[SubwayArrival]:
        """Get arrivals for a specific station."""
        all_arrivals = await self.get_all_arrivals()
        return [a for a in all_arrivals if a.station_code == station_code]

    async def get_trip_stops(self, trip_id: str) -> list[SubwayArrival]:
        """Get all stops for a specific trip, sorted by arrival time."""
        all_arrivals = await self.get_all_arrivals()
        trip_stops = [a for a in all_arrivals if a.trip_id == trip_id]
        return sorted(trip_stops, key=lambda a: a.arrival_time)

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_times.clear()
