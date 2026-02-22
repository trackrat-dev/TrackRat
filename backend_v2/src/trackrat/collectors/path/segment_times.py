"""GTFS-based segment travel times for PATH trains.

Loads per-segment travel times from GTFS static data to replace the
hardcoded 3 min/segment approximation. Uses one representative trip
per PATH route to extract inter-stop travel time ratios.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.stations import PATH_ROUTE_STOPS
from trackrat.models.database import GTFSRoute, GTFSTrip

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

    For each PATH route, finds one representative trip and computes
    the travel time between consecutive stops.

    Args:
        db: Database session

    Returns:
        Map from route_id to list of (from_station, to_station, minutes) tuples
    """
    result: SegmentTimesMap = {}

    # Get all PATH routes from GTFS
    stmt = select(GTFSRoute).where(GTFSRoute.data_source == "PATH")
    routes = (await db.scalars(stmt)).all()

    if not routes:
        logger.warning("path_no_gtfs_routes_found")
        return result

    for route in routes:
        route_id_str = route.route_id
        if not route_id_str:
            continue
        expected_stops = PATH_ROUTE_STOPS.get(route_id_str)
        if not expected_stops:
            continue

        # Find one representative trip for this route
        trip_stmt = (
            select(GTFSTrip)
            .where(GTFSTrip.route_id == route.id)
            .options(selectinload(GTFSTrip.stop_times))
            .limit(1)
        )
        trip = await db.scalar(trip_stmt)
        if not trip or not trip.stop_times:
            continue

        # Sort stop_times by sequence
        sorted_times = sorted(trip.stop_times, key=lambda st: st.stop_sequence or 0)

        # Build station_code -> departure_time_seconds map
        station_times: dict[str, int] = {}
        for st in sorted_times:
            if st.station_code and st.departure_time:
                station_times[st.station_code] = _parse_gtfs_time_to_seconds(
                    st.departure_time
                )
            elif st.station_code and st.arrival_time:
                station_times[st.station_code] = _parse_gtfs_time_to_seconds(
                    st.arrival_time
                )

        # Check if GTFS stop order matches our expected order
        # If reversed, we still extract correct segment times by matching
        # against expected_stops order
        gtfs_station_order = [st.station_code for st in sorted_times if st.station_code]

        # Determine if GTFS trip is in reverse direction
        if len(gtfs_station_order) >= 2 and len(expected_stops) >= 2:
            first_gtfs = gtfs_station_order[0]
            if (
                first_gtfs in expected_stops
                and expected_stops.index(first_gtfs) == len(expected_stops) - 1
            ):
                # GTFS trip is reversed relative to our route definition
                # That's OK - we just need the absolute travel times between stations
                pass

        # Extract segment times following expected_stops order
        segments: list[tuple[str, str, float]] = []
        for i in range(len(expected_stops) - 1):
            from_station = expected_stops[i]
            to_station = expected_stops[i + 1]

            if from_station in station_times and to_station in station_times:
                time_diff = abs(station_times[to_station] - station_times[from_station])
                minutes = time_diff / 60.0
                # Sanity check: segment time should be 1-15 minutes
                if 0.5 <= minutes <= 15.0:
                    segments.append((from_station, to_station, minutes))
                else:
                    logger.warning(
                        "path_gtfs_segment_time_outlier",
                        route_id=route_id_str,
                        from_station=from_station,
                        to_station=to_station,
                        minutes=minutes,
                    )
                    segments.append(
                        (from_station, to_station, DEFAULT_MINUTES_PER_SEGMENT)
                    )
            else:
                # Missing station in GTFS data - use default
                segments.append((from_station, to_station, DEFAULT_MINUTES_PER_SEGMENT))

        if segments:
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
        # Build a quick lookup: (from, to) -> minutes
        segment_lookup: dict[tuple[str, str], float] = {
            (s[0], s[1]): s[2] for s in segments
        }

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
