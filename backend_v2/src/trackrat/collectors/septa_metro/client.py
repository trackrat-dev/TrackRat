"""SEPTA Metro GTFS-RT client.

The SEPTA "septa-pa-us" feed carries the whole surface network (bus, trolley,
subway). This client filters to the Metro rail routes only (subway + trolley,
the route_ids in ``SEPTA_METRO_ROUTES``) and returns absolute-time arrivals —
unlike Regional Rail, the Metro feed provides real ``arrival``/``departure``
times and ``stop_id`` values. Public feed, no authentication.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.collectors.septa_common import SeptaFeedFetchError
from trackrat.config.stations import (
    SEPTA_METRO_GTFS_RT_FEED_URL,
    SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP,
    SEPTA_METRO_ROUTES,
)
from trackrat.utils.logging import get_logger

logger = get_logger(__name__)


class SeptaMetroArrival(BaseModel):
    """A single arrival/stop time from the SEPTA Metro GTFS-RT feed."""

    station_code: str
    gtfs_stop_id: str
    trip_id: str
    route_id: str
    direction_id: int
    headsign: str | None
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class SeptaMetroClient:
    """Fetches SEPTA Metro real-time arrivals, filtered to Metro rail routes."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._cache: list[SeptaMetroArrival] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # seconds

    @property
    def session(self) -> httpx.AsyncClient:
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (SEPTA Metro Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "SeptaMetroClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _is_cache_valid(self) -> bool:
        if self._cache is None or self._cache_time is None:
            return False
        age = (datetime.now(UTC) - self._cache_time).total_seconds()
        return age < self._cache_ttl

    @staticmethod
    def parse_feed(content: bytes) -> list[SeptaMetroArrival]:
        """Parse a GTFS-RT protobuf payload into Metro arrivals (pure function)."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)

        arrivals: list[SeptaMetroArrival] = []
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            tu = entity.trip_update
            trip = tu.trip
            route_id = trip.route_id if trip.HasField("route_id") else ""
            # Metro rail routes only — the feed also carries buses and trolleybuses.
            if route_id not in SEPTA_METRO_ROUTES:
                continue

            trip_id = trip.trip_id if trip.HasField("trip_id") else ""
            direction_id = trip.direction_id if trip.HasField("direction_id") else 0

            for stu in tu.stop_time_update:
                gtfs_stop_id = stu.stop_id if stu.HasField("stop_id") else ""
                station_code = SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
                if not station_code:
                    continue

                arrival_time: datetime | None = None
                delay_seconds = 0
                if stu.HasField("arrival"):
                    arr = stu.arrival
                    if arr.HasField("time") and arr.time:
                        arrival_time = datetime.fromtimestamp(arr.time, tz=UTC)
                    if arr.HasField("delay"):
                        delay_seconds = arr.delay

                departure_time: datetime | None = None
                if stu.HasField("departure"):
                    dep = stu.departure
                    if dep.HasField("time") and dep.time:
                        departure_time = datetime.fromtimestamp(dep.time, tz=UTC)

                if arrival_time is None:
                    if departure_time is None:
                        continue
                    arrival_time = departure_time

                arrivals.append(
                    SeptaMetroArrival(
                        station_code=station_code,
                        gtfs_stop_id=gtfs_stop_id,
                        trip_id=trip_id,
                        route_id=route_id,
                        direction_id=direction_id,
                        headsign=None,
                        arrival_time=arrival_time,
                        departure_time=departure_time,
                        delay_seconds=delay_seconds,
                        track=None,
                    )
                )
        return arrivals

    async def get_all_arrivals(
        self, *, use_cache: bool = True
    ) -> list[SeptaMetroArrival]:
        """Fetch and parse all Metro arrivals (cached within TTL)."""
        if use_cache and self._is_cache_valid():
            return self._cache or []

        try:
            response = await self.session.get(SEPTA_METRO_GTFS_RT_FEED_URL)
            response.raise_for_status()
            arrivals = self.parse_feed(response.content)
            self._cache = arrivals
            self._cache_time = datetime.now(UTC)
            logger.info(f"Fetched {len(arrivals)} SEPTA Metro arrivals from feed")
            return arrivals
        except httpx.HTTPStatusError as e:
            logger.error(
                "septa_metro_feed_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise SeptaFeedFetchError("SEPTA Metro feed returned an HTTP error") from e
        except httpx.HTTPError as e:
            logger.error(
                "septa_metro_feed_network_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise SeptaFeedFetchError("SEPTA Metro feed request failed") from e
        except Exception as e:
            logger.error(
                "septa_metro_feed_parse_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise SeptaFeedFetchError("SEPTA Metro feed could not be parsed") from e

    def clear_cache(self) -> None:
        self._cache = None
        self._cache_time = None
