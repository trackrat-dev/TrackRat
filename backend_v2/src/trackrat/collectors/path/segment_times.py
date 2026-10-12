"""GTFS-based segment travel times for PATH trains.

Loads per-segment travel times from GTFS static data to replace the
hardcoded 3 min/segment approximation. Each segment's time is the median
across every PATH trip that runs it.
"""

from collections import defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import PATH_ROUTE_STOPS
from trackrat.models.database import GTFSRoute, GTFSStopTime, GTFSTrip

logger = get_logger(__name__)

# Type alias: route_id -> list of (from_station, to_station, minutes)
SegmentTimesMap = dict[str, list[tuple[str, str, float]]]

# Default fallback when GTFS data is unavailable
DEFAULT_MINUTES_PER_SEGMENT = 3.0

# Module-level cache
_cached_segment_times: SegmentTimesMap | None = None


def _parse_gtfs_time_to_seconds(time_str: str) -> int:
    """Parse GTFS time string (HH:MM:SS) to seconds since midnight.

    Handles times > 24:00:00 for trips crossing midnight.

    Args:
        time_str: Time in HH:MM:SS format (e.g., "25:30:00")

    Returns:
        Seconds since midnight
    """
    parts = time_str.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


async def _load_segment_times_from_gtfs(db: AsyncSession) -> SegmentTimesMap:
    """Load segment travel times from GTFS static data.

    Each segment's time is the median across every PATH trip that runs it, in
    either direction. One representative trip per route is not safe: the feed
    mixes the regular timetable with construction and holiday variants that
    hold trains 5-10 minutes at JSQ or WTC, and it lists them first. Whichever
    trip ``LIMIT 1`` returned baked its hold into a segment, enough on its own
    to split one train into two journeys (issue #1752).

    Args:
        db: Database session

    Returns:
        Map from route_id to list of (from_station, to_station, minutes) tuples
    """
    result: SegmentTimesMap = {}

    stmt = (
        select(
            GTFSRoute.route_id,
            GTFSStopTime.trip_id,
            GTFSStopTime.station_code,
            GTFSStopTime.departure_time,
            GTFSStopTime.arrival_time,
        )
        .join(GTFSTrip, GTFSStopTime.trip_id == GTFSTrip.id)
        .join(GTFSRoute, GTFSTrip.route_id == GTFSRoute.id)
        .where(GTFSRoute.data_source == "PATH")
        .order_by(GTFSStopTime.trip_id, GTFSStopTime.stop_sequence)
    )

    # (route_id, {station, station}) -> minutes for each trip running that hop
    observed: dict[tuple[str, frozenset[str]], list[float]] = defaultdict(list)
    previous: tuple[int, str, int] | None = None  # (trip_id, station, seconds)
    async for route_id, trip_id, station_code, departure, arrival in await db.stream(
        stmt
    ):
        time_str = departure or arrival
        if not station_code or not time_str:
            continue
        seconds = _parse_gtfs_time_to_seconds(time_str)
        if previous is not None and previous[0] == trip_id:
            hop = frozenset((previous[1], station_code))
            observed[(route_id, hop)].append(abs(seconds - previous[2]) / 60.0)
        previous = (trip_id, station_code, seconds)

    if not observed:
        logger.warning("path_no_gtfs_routes_found")
        return result

    for route_id_str, expected_stops in PATH_ROUTE_STOPS.items():
        segments: list[tuple[str, str, float]] = []
        found_any = False
        for from_station, to_station in zip(
            expected_stops, expected_stops[1:], strict=False
        ):
            times = observed.get((route_id_str, frozenset((from_station, to_station))))
            if not times:
                # No trip runs this hop - use default
                segments.append((from_station, to_station, DEFAULT_MINUTES_PER_SEGMENT))
                continue
            found_any = True
            minutes = median(times)
            # Sanity check: segment time should be 1-15 minutes
            if not 0.5 <= minutes <= 15.0:
                logger.warning(
                    "path_gtfs_segment_time_outlier",
                    route_id=route_id_str,
                    from_station=from_station,
                    to_station=to_station,
                    minutes=minutes,
                )
                minutes = DEFAULT_MINUTES_PER_SEGMENT
            segments.append((from_station, to_station, minutes))

        if found_any:
            result[route_id_str] = segments
            logger.debug(
                "path_gtfs_segment_times_loaded",
                route_id=route_id_str,
                segments=len(segments),
                total_minutes=sum(s[2] for s in segments),
            )

    logger.info(
        "path_segment_times_loaded",
        routes_loaded=len(result),
        routes_expected=len(PATH_ROUTE_STOPS),
    )
    return result


async def get_segment_times(db: AsyncSession) -> SegmentTimesMap:
    """Get segment travel times, loading from GTFS on first call.

    Results are cached in-memory for the lifetime of the process.

    Args:
        db: Database session

    Returns:
        Map from route_id to list of segment times
    """
    global _cached_segment_times
    if _cached_segment_times is not None:
        return _cached_segment_times

    try:
        _cached_segment_times = await _load_segment_times_from_gtfs(db)
    except Exception as e:
        logger.error("path_segment_times_load_failed", error=str(e))
        _cached_segment_times = {}

    return _cached_segment_times


def get_cumulative_time(
    segment_times: SegmentTimesMap,
    route_stops: list[str],
    from_idx: int,
    to_idx: int,
    route_id: str | None,
) -> float:
    """Calculate cumulative travel time between two stop indices.

    Pure function that sums segment travel times between from_idx and to_idx.
    Falls back to DEFAULT_MINUTES_PER_SEGMENT per segment if GTFS data
    is unavailable for this route.

    Args:
        segment_times: Map from route_id to segment time data
        route_stops: Ordered list of station codes for this journey
        from_idx: Index of the starting stop (0-based)
        to_idx: Index of the ending stop (0-based)
        route_id: GTFS route ID for looking up segment times

    Returns:
        Travel time in minutes from route_stops[from_idx] to route_stops[to_idx]
    """
    if from_idx == to_idx:
        return 0.0

    # Ensure from < to
    if from_idx > to_idx:
        from_idx, to_idx = to_idx, from_idx

    num_segments = to_idx - from_idx

    # Try to use GTFS-based times
    if route_id and route_id in segment_times:
        segments = segment_times[route_id]
        # Segments are stored in PATH_ROUTE_STOPS order, but trains running the
        # other way pass their stop list reversed — key both orders, or that
        # whole direction falls back to the flat default (issue #1752).
        segment_lookup: dict[tuple[str, str], float] = {}
        for from_station, to_station, minutes in segments:
            segment_lookup[(from_station, to_station)] = minutes
            segment_lookup[(to_station, from_station)] = minutes

        total = 0.0
        all_found = True
        for i in range(from_idx, to_idx):
            if i + 1 < len(route_stops):
                key = (route_stops[i], route_stops[i + 1])
                if key in segment_lookup:
                    total += segment_lookup[key]
                else:
                    all_found = False
                    break

        if all_found:
            return total

    # Fallback: use default minutes per segment
    return num_segments * DEFAULT_MINUTES_PER_SEGMENT


def clear_cache() -> None:
    """Clear the cached segment times. Used for testing."""
    global _cached_segment_times
    _cached_segment_times = None
