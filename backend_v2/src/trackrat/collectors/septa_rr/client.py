"""SEPTA Regional Rail GTFS-RT client.

SEPTA's Regional Rail TripUpdates feed is **delay-based**: each stop_time_update
carries a ``delay`` (seconds relative to the published schedule) keyed by
``stop_sequence`` — it has no ``stop_id`` and no absolute times. Absolute times
are reconstructed by the collector, which joins the GTFS static schedule by
``(trip_id, stop_sequence)`` and applies the delay.

The feed is public (no authentication). A trip_id matches the static feed's
trip_id exactly (e.g. ``CHW8312_20260718_SID189411``), but its embedded
``_YYYYMMDD_`` segment is a schedule-version tag bound to the ``service_id`` — NOT
the operating date (it is served for weeks and is identical across many days). The
collector therefore joins against the static schedule for the current operating
day, never the trip_id's date (see
``SeptaRailCollector._resolve_static_schedule``).
"""

from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel

from trackrat.config.stations import SEPTA_RR_GTFS_RT_FEED_URL, SEPTA_RR_ROUTES
from trackrat.utils.logging import get_logger

logger = get_logger(__name__)


class SeptaRailStopUpdate(BaseModel):
    """A single delay-based stop_time_update from the feed."""

    stop_sequence: int
    arrival_delay: int | None
    departure_delay: int | None


class SeptaRailTripUpdate(BaseModel):
    """One trip's worth of delay updates, before the static-schedule join."""

    trip_id: str
    route_id: str
    direction_id: int
    vehicle_label: str | None
    stop_updates: list[SeptaRailStopUpdate]


class SeptaRailArrival(BaseModel):
    """A resolved per-stop arrival (absolute times), consumed by ``mta_common``.

    Built by the collector from a :class:`SeptaRailTripUpdate` plus the GTFS
    static schedule. Shares the attribute surface the shared MTA helpers expect
    (``station_code``, ``arrival_time``, ``departure_time``, ``delay_seconds``,
    ``track``, ``trip_id``).
    """

    station_code: str
    trip_id: str
    route_id: str
    direction_id: int
    arrival_time: datetime
    departure_time: datetime | None
    delay_seconds: int
    track: str | None

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class SeptaRailClient:
    """Fetches and parses SEPTA Regional Rail delay-based TripUpdates."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._cache: list[SeptaRailTripUpdate] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # seconds

    @property
    def session(self) -> httpx.AsyncClient:
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "TrackRat/2.0 (SEPTA Regional Rail Tracker)",
                    "Accept": "application/x-protobuf",
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "SeptaRailClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _is_cache_valid(self) -> bool:
        if self._cache is None or self._cache_time is None:
            return False
        age = (datetime.now(UTC) - self._cache_time).total_seconds()
        return age < self._cache_ttl

    @staticmethod
    def parse_feed(content: bytes) -> list[SeptaRailTripUpdate]:
        """Parse a GTFS-RT protobuf payload into trip updates (pure function)."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)

        trip_updates: list[SeptaRailTripUpdate] = []
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            tu = entity.trip_update
            trip = tu.trip
            route_id = trip.route_id if trip.HasField("route_id") else ""
            # Only Regional Rail routes (the feed is RR-only, but guard anyway).
            if route_id not in SEPTA_RR_ROUTES:
                continue

            stop_updates: list[SeptaRailStopUpdate] = []
            for stu in tu.stop_time_update:
                arr_delay = (
                    stu.arrival.delay
                    if stu.HasField("arrival") and stu.arrival.HasField("delay")
                    else None
                )
                dep_delay = (
                    stu.departure.delay
                    if stu.HasField("departure") and stu.departure.HasField("delay")
                    else None
                )
                if arr_delay is None and dep_delay is None:
                    continue
                stop_updates.append(
                    SeptaRailStopUpdate(
                        stop_sequence=stu.stop_sequence,
                        arrival_delay=arr_delay,
                        departure_delay=dep_delay,
                    )
                )

            if not stop_updates:
                continue

            trip_updates.append(
                SeptaRailTripUpdate(
                    trip_id=trip.trip_id if trip.HasField("trip_id") else "",
                    route_id=route_id,
                    direction_id=(
                        trip.direction_id if trip.HasField("direction_id") else 0
                    ),
                    vehicle_label=(
                        tu.vehicle.id
                        if tu.HasField("vehicle") and tu.vehicle.id
                        else None
                    ),
                    stop_updates=stop_updates,
                )
            )
        return trip_updates

    async def get_trip_updates(self) -> list[SeptaRailTripUpdate]:
        """Fetch and parse all Regional Rail trip updates (cached within TTL)."""
        if self._is_cache_valid():
            return self._cache or []

        try:
            response = await self.session.get(SEPTA_RR_GTFS_RT_FEED_URL)
            response.raise_for_status()
            trip_updates = self.parse_feed(response.content)
            self._cache = trip_updates
            self._cache_time = datetime.now(UTC)
            logger.info(f"Fetched {len(trip_updates)} SEPTA RR trip updates")
            return trip_updates
        except httpx.HTTPStatusError as e:
            logger.error(
                "septa_rr_feed_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            return self._cache or []
        except httpx.HTTPError as e:
            logger.error(
                "septa_rr_feed_network_error", error=str(e), error_type=type(e).__name__
            )
            return self._cache or []
        except Exception as e:
            logger.error(
                "septa_rr_feed_parse_error", error=str(e), error_type=type(e).__name__
            )
            return self._cache or []

    def clear_cache(self) -> None:
        self._cache = None
        self._cache_time = None
