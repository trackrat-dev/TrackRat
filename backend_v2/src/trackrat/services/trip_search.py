"""
Trip search service for finding direct and transfer-based trips.

When a direct service exists between two stations, returns single-leg trips.
When no direct service exists, finds 1-transfer connections by matching
real-time departures at transfer points between transit systems.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import get_station_name
from trackrat.config.transfer_points import (
    TransferPoint,
    get_intra_subway_transfers,
    get_subway_lines_at_station,
    get_systems_serving_station,
    get_transfer_points,
)
from trackrat.models.api import (
    SimpleStationInfo,
    StationInfo,
    TrainDeparture,
    TransferInfo,
    TripLeg,
    TripOption,
    TripSearchResponse,
)
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Maximum number of departure queries per transfer search to keep response fast
MAX_TRANSFER_QUERIES = 6

# Minimum number of minutes after arrival to allow for catching the next train
# (in addition to the transfer point's walk_minutes)
CONNECTION_BUFFER_MINUTES = 2

# Maximum connection wait time at the transfer station (minutes)
MAX_CONNECTION_WAIT_MINUTES = 60


def _get_best_time(info: StationInfo) -> datetime | None:
    """Get the best available time from a StationInfo (actual > updated > scheduled)."""
    return info.actual_time or info.updated_time or info.scheduled_time


def _departure_to_leg(dep: TrainDeparture) -> TripLeg:
    """Convert a TrainDeparture into a TripLeg."""
    return TripLeg(
        train_id=dep.train_id,
        journey_date=dep.journey_date,
        line=dep.line,
        data_source=dep.data_source,
        destination=dep.destination,
        boarding=dep.departure,
        alighting=dep.arrival or dep.departure,  # fallback if no arrival
        observation_type=dep.observation_type,
        is_cancelled=dep.is_cancelled,
        train_position=dep.train_position,
    )


def _make_direct_trip(dep: TrainDeparture) -> TripOption | None:
    """Convert a direct TrainDeparture into a single-leg TripOption."""
    departure_time = _get_best_time(dep.departure)
    arrival_time = _get_best_time(dep.arrival) if dep.arrival else None
    if not departure_time:
        return None

    leg = _departure_to_leg(dep)

    duration = 0
    if arrival_time and departure_time:
        duration = max(0, int((arrival_time - departure_time).total_seconds() / 60))

    return TripOption(
        legs=[leg],
        transfers=[],
        departure_time=departure_time,
        arrival_time=arrival_time or departure_time,
        total_duration_minutes=duration,
        is_direct=True,
    )


def _find_relevant_transfer_points(
    from_systems: set[str],
    to_systems: set[str],
    from_station: str = "",
    to_station: str = "",
) -> list[TransferPoint]:
    """Find transfer points connecting from-systems to to-systems.

    For cross-system pairs (e.g., NJT→PATH), returns all transfer points.
    For intra-subway (both SUBWAY), filters to complexes where one side
    shares lines with the origin and the other shares lines with the destination.
    """
    transfers: list[TransferPoint] = []
    seen: set[frozenset[tuple[str, str]]] = set()

    # Cross-system transfers (existing logic)
    for sys_from in from_systems:
        for sys_to in to_systems:
            if sys_from == sys_to:
                continue
            for tp in get_transfer_points(sys_from, sys_to):
                key = frozenset(
                    {(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)}
                )
                if key not in seen:
                    seen.add(key)
                    transfers.append(tp)

    # Intra-subway transfers: find complexes connecting origin's lines to dest's lines.
    # We don't skip when lines overlap — even if origin and dest share a line,
    # direct service may not cover the segment, so a transfer via a different
    # line can still be the best (or only) option.
    if (
        "SUBWAY" in from_systems
        and "SUBWAY" in to_systems
        and from_station
        and to_station
    ):
        origin_lines = get_subway_lines_at_station(from_station)
        dest_lines = get_subway_lines_at_station(to_station)
        if origin_lines and dest_lines:
            for tp in get_intra_subway_transfers():
                # One side must share lines with origin, other with destination
                a_has_origin = bool(tp.lines_a & origin_lines)
                b_has_origin = bool(tp.lines_b & origin_lines)
                a_has_dest = bool(tp.lines_a & dest_lines)
                b_has_dest = bool(tp.lines_b & dest_lines)
                if (a_has_origin and b_has_dest) or (b_has_origin and a_has_dest):
                    key = frozenset(
                        {(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)}
                    )
                    if key not in seen:
                        seen.add(key)
                        transfers.append(tp)

    return transfers


def _orient_transfer(
    tp: TransferPoint,
    from_systems: set[str],
    to_systems: set[str],
    from_station: str = "",
    to_station: str = "",
) -> tuple[str, str, str, str]:
    """Orient a transfer point: returns (alight_station, alight_system, board_station, board_system).

    The alight station is on the from-side system (where you get off leg 1).
    The board station is on the to-side system (where you board leg 2).

    For intra-subway transfers (system_a == system_b), uses line overlap
    with origin/destination to determine orientation.
    """
    # Intra-subway: orient by line overlap with origin/destination
    if tp.system_a == tp.system_b and tp.lines_a and tp.lines_b and from_station:
        origin_lines = get_subway_lines_at_station(from_station)
        if tp.lines_a & origin_lines:
            return tp.station_a, tp.system_a, tp.station_b, tp.system_b
        return tp.station_b, tp.system_b, tp.station_a, tp.system_a

    # Cross-system: orient by system membership (existing logic)
    if tp.system_a in from_systems and tp.system_b in to_systems:
        return tp.station_a, tp.system_a, tp.station_b, tp.system_b
    elif tp.system_b in from_systems and tp.system_a in to_systems:
        return tp.station_b, tp.system_b, tp.station_a, tp.system_a
    # Both sides could be from-side or to-side; pick the first valid orientation
    if tp.system_a in from_systems:
        return tp.station_a, tp.system_a, tp.station_b, tp.system_b
    return tp.station_b, tp.system_b, tp.station_a, tp.system_a


async def search_trips(
    db: AsyncSession,
    from_station: str,
    to_station: str,
    search_date: date | None = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
    hide_departed: bool = False,
    data_sources: list[str] | None = None,
    limit: int = 10,
) -> TripSearchResponse:
    """Search for trips between two stations, including transfers.

    1. Try direct service first (reuses DepartureService)
    2. If no direct results, find transfer connections
    """
    departure_service = DepartureService()

    logger.info(
        "trip_search_started",
        from_station=from_station,
        to_station=to_station,
        hide_departed=hide_departed,
        data_sources=data_sources,
    )

    # --- Step 1: Try direct service ---
    direct_response = await departure_service.get_departures(
        db=db,
        from_station=from_station,
        to_station=to_station,
        date=search_date,
        time_from=time_from,
        time_to=time_to,
        limit=limit,
        hide_departed=hide_departed,
        data_sources=data_sources,
        skip_individual_refresh=False,
    )

    if direct_response.departures:
        trips = []
        for dep in direct_response.departures:
            trip = _make_direct_trip(dep)
            if trip:
                trips.append(trip)
        logger.info("trip_search_direct", count=len(trips))
        return TripSearchResponse(
            trips=trips,
            metadata={
                "from_station": {
                    "code": from_station,
                    "name": get_station_name(from_station),
                },
                "to_station": {
                    "code": to_station,
                    "name": get_station_name(to_station),
                },
                "count": len(trips),
                "search_type": "direct",
                "generated_at": now_et().isoformat(),
            },
        )

    # --- Step 2: No direct service — find transfers ---
    from_systems = get_systems_serving_station(from_station)
    to_systems = get_systems_serving_station(to_station)

    if not from_systems or not to_systems:
        return _empty_response(from_station, to_station, "no_systems")

    # Find transfer points between systems (cross-system and intra-subway).
    transfer_points = _find_relevant_transfer_points(
        from_systems, to_systems, from_station, to_station
    )
    if not transfer_points:
        return _empty_response(from_station, to_station, "no_transfer_points")

    # Query departures for each transfer point
    transfer_trips: list[TripOption] = []
    queries_made = 0
    transfer_points_checked = 0

    for tp in transfer_points:
        if queries_made >= MAX_TRANSFER_QUERIES:
            break
        transfer_points_checked += 1

        alight_station, alight_system, board_station, board_system = _orient_transfer(
            tp, from_systems, to_systems, from_station, to_station
        )

        # Leg 1: from_station -> alight_station (system of from_station)
        leg1_response = await departure_service.get_departures(
            db=db,
            from_station=from_station,
            to_station=alight_station,
            date=search_date,
            time_from=time_from,
            time_to=time_to,
            limit=20,  # Get enough candidates for matching
            hide_departed=hide_departed,
            data_sources=[alight_system],
            skip_individual_refresh=True,
        )
        queries_made += 1

        if not leg1_response.departures:
            continue

        # Leg 2: board_station -> to_station (system of to_station)
        # Start leg 2 from the earliest leg 1 departure time so that the
        # limited result set (20 departures) covers the connection window
        # instead of being consumed by old, irrelevant departures.
        leg2_time_from = _get_best_time(leg1_response.departures[0].departure)
        leg2_response = await departure_service.get_departures(
            db=db,
            from_station=board_station,
            to_station=to_station,
            date=search_date,
            time_from=leg2_time_from,
            time_to=None,
            limit=20,
            hide_departed=False,  # Don't hide — we need future departures to match
            data_sources=[board_system],
            skip_individual_refresh=True,
        )
        queries_made += 1

        if not leg2_response.departures:
            continue

        # Match connections: leg1 arrival + transfer time <= leg2 departure
        transfer_minutes = tp.walk_minutes + CONNECTION_BUFFER_MINUTES

        for dep1 in leg1_response.departures:
            if dep1.is_cancelled:
                continue
            if not dep1.arrival:
                continue
            leg1_arrival = _get_best_time(dep1.arrival)
            if not leg1_arrival:
                continue

            earliest_leg2 = leg1_arrival + timedelta(minutes=transfer_minutes)
            latest_leg2 = leg1_arrival + timedelta(minutes=MAX_CONNECTION_WAIT_MINUTES)

            for dep2 in leg2_response.departures:
                if dep2.is_cancelled:
                    continue
                leg2_departure = _get_best_time(dep2.departure)
                if not leg2_departure:
                    continue
                if leg2_departure < earliest_leg2:
                    continue
                if leg2_departure > latest_leg2:
                    break  # Departures are sorted by time, no more valid matches

                leg2_arrival = _get_best_time(dep2.arrival) if dep2.arrival else None
                if not leg2_arrival:
                    continue

                leg1_departure = _get_best_time(dep1.departure)
                if not leg1_departure:
                    continue

                total_duration = max(
                    0, int((leg2_arrival - leg1_departure).total_seconds() / 60)
                )

                trip = TripOption(
                    legs=[
                        _departure_to_leg(dep1),
                        _departure_to_leg(dep2),
                    ],
                    transfers=[
                        TransferInfo(
                            from_station=SimpleStationInfo(
                                code=alight_station,
                                name=get_station_name(alight_station),
                            ),
                            to_station=SimpleStationInfo(
                                code=board_station,
                                name=get_station_name(board_station),
                            ),
                            walk_minutes=tp.walk_minutes,
                            same_station=tp.same_station,
                        ),
                    ],
                    departure_time=leg1_departure,
                    arrival_time=leg2_arrival,
                    total_duration_minutes=total_duration,
                    is_direct=False,
                )
                transfer_trips.append(trip)
                break  # Only take the first matching leg2 for this leg1

    # Sort by departure time, then total duration
    transfer_trips.sort(key=lambda t: (t.departure_time, t.total_duration_minutes))
    transfer_trips = transfer_trips[:limit]

    logger.info(
        "trip_search_transfer",
        count=len(transfer_trips),
        transfer_points_checked=transfer_points_checked,
        queries_made=queries_made,
    )

    return TripSearchResponse(
        trips=transfer_trips,
        metadata={
            "from_station": {
                "code": from_station,
                "name": get_station_name(from_station),
            },
            "to_station": {"code": to_station, "name": get_station_name(to_station)},
            "count": len(transfer_trips),
            "search_type": "transfer",
            "transfer_points_checked": transfer_points_checked,
            "generated_at": now_et().isoformat(),
        },
    )


def _empty_response(
    from_station: str, to_station: str, reason: str
) -> TripSearchResponse:
    """Build an empty TripSearchResponse with metadata."""
    return TripSearchResponse(
        trips=[],
        metadata={
            "from_station": {
                "code": from_station,
                "name": get_station_name(from_station),
            },
            "to_station": {"code": to_station, "name": get_station_name(to_station)},
            "count": 0,
            "search_type": reason,
            "generated_at": now_et().isoformat(),
        },
    )
