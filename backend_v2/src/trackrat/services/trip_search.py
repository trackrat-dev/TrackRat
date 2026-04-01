"""
Trip search service for finding direct and transfer-based trips.

When a direct service exists between two stations, returns single-leg trips.
When no direct service exists, finds 1-transfer connections by matching
real-time departures at transfer points between transit systems.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import get_station_name
from trackrat.config.transfer_points import (
    TransferPoint,
    get_intra_system_transfers,
    get_station_lines,
    get_subway_lines_at_station,
    get_systems_serving_station,
    get_transfer_points,
)
from trackrat.db.engine import get_session
from trackrat.models.api import (
    DeparturesResponse,
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


def _filter_unreasonable_durations(trips: list[TripOption]) -> list[TripOption]:
    """Remove trips that are disproportionately longer than the fastest option.

    Keeps alternatives within 2x the fastest duration or +20 min, whichever is
    more generous.  The +20 min floor prevents over-aggressive filtering on short
    trips (e.g. a 12-min trip wouldn't exclude a 22-min alternative).
    """
    if not trips:
        return trips
    min_dur = min(t.total_duration_minutes for t in trips)
    max_reasonable = max(min_dur * 2.0, min_dur + 20)
    return [t for t in trips if t.total_duration_minutes <= max_reasonable]


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

    # Intra-system transfers: find junction points connecting origin's lines to
    # dest's lines within the same system. Works for SUBWAY (complexes),
    # PATH (junction at Journal Sq), BART (branching lines), etc.
    # We don't skip when lines overlap — even if origin and dest share a line,
    # direct service may not cover the segment, so a transfer via a different
    # line can still be the best (or only) option.
    if from_station and to_station:
        common_systems = from_systems & to_systems
        for system in common_systems:
            origin_lines = get_station_lines(from_station, system)
            dest_lines = get_station_lines(to_station, system)
            if origin_lines and dest_lines:
                for tp in get_intra_system_transfers(system):
                    # One side must share lines with origin, other with dest
                    a_has_origin = bool(tp.lines_a & origin_lines)
                    b_has_origin = bool(tp.lines_b & origin_lines)
                    a_has_dest = bool(tp.lines_a & dest_lines)
                    b_has_dest = bool(tp.lines_b & dest_lines)
                    if (a_has_origin and b_has_dest) or (
                        b_has_origin and a_has_dest
                    ):
                        key = frozenset(
                            {
                                (tp.station_a, tp.system_a),
                                (tp.station_b, tp.system_b),
                            }
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
    # Intra-system transfer: orient by line overlap with origin/destination
    if tp.system_a == tp.system_b and tp.lines_a and tp.lines_b and from_station:
        origin_lines = get_station_lines(from_station, tp.system_a)
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

    # Restrict to user-enabled systems so transfer search doesn't
    # propose routes through systems the user hasn't selected.
    if data_sources:
        allowed = set(data_sources)
        from_systems = from_systems & allowed
        to_systems = to_systems & allowed

    if not from_systems or not to_systems:
        return _empty_response(from_station, to_station, "no_systems")

    # Find transfer points between systems (cross-system and intra-subway).
    transfer_points = _find_relevant_transfer_points(
        from_systems, to_systems, from_station, to_station
    )
    if not transfer_points:
        return _empty_response(from_station, to_station, "no_transfer_points")

    # Prepare transfer point queries — orient each transfer point up front
    # Limit to MAX_TRANSFER_QUERIES / 2 transfer points (each needs 2 queries)
    max_transfer_points = MAX_TRANSFER_QUERIES // 2
    oriented_transfers: list[tuple[TransferPoint, str, str, str, str]] = []
    for tp in transfer_points:
        if len(oriented_transfers) >= max_transfer_points:
            break
        alight_station, alight_system, board_station, board_system = _orient_transfer(
            tp, from_systems, to_systems, from_station, to_station
        )
        oriented_transfers.append(
            (tp, alight_station, alight_system, board_station, board_system)
        )

    transfer_points_checked = len(oriented_transfers)

    # Fire all leg queries in parallel using separate DB sessions.
    # Each transfer point needs leg1 (origin -> transfer) and leg2 (transfer -> dest).
    # Using separate sessions is required because AsyncSession is not concurrency-safe.
    #
    async def _query_leg(
        leg_from: str,
        leg_to: str,
        leg_date: date | None,
        leg_time_from: datetime | None,
        leg_time_to: datetime | None,
        leg_hide_departed: bool,
        leg_data_sources: list[str],
    ) -> DeparturesResponse:
        async with get_session() as leg_db:
            return await departure_service.get_departures(
                db=leg_db,
                from_station=leg_from,
                to_station=leg_to,
                date=leg_date,
                time_from=leg_time_from,
                time_to=leg_time_to,
                limit=20,
                hide_departed=leg_hide_departed,
                data_sources=leg_data_sources,
                skip_individual_refresh=True,
            )

    # Build all tasks: for each transfer point, leg1 and leg2
    leg_tasks: list[tuple[int, str]] = []  # (transfer_idx, "leg1"|"leg2")
    coros = []
    for i, (
        _tp,
        alight_station,
        alight_system,
        board_station,
        board_system,
    ) in enumerate(oriented_transfers):
        # Leg 1: from_station -> alight_station
        coros.append(
            _query_leg(
                from_station,
                alight_station,
                search_date,
                time_from,
                time_to,
                hide_departed,
                [alight_system],
            )
        )
        leg_tasks.append((i, "leg1"))

        # Leg 2: board_station -> to_station
        # No time_from/time_to — leg 1 may arrive after original window
        coros.append(
            _query_leg(
                board_station,
                to_station,
                search_date,
                None,
                None,
                False,
                [board_system],
            )
        )
        leg_tasks.append((i, "leg2"))

    # Execute all leg queries concurrently
    results = await asyncio.gather(*coros, return_exceptions=True)

    # Group results by transfer point index
    leg_responses: dict[int, dict[str, DeparturesResponse]] = {}
    for (idx, leg_name), result in zip(leg_tasks, results, strict=False):
        if isinstance(result, BaseException):
            logger.warning(
                "transfer_leg_query_failed",
                transfer_idx=idx,
                leg=leg_name,
                error=str(result),
            )
            continue
        leg_responses.setdefault(idx, {})[leg_name] = result

    queries_made = len([r for r in results if not isinstance(r, BaseException)])

    # Match connections from parallel results
    transfer_trips: list[TripOption] = []
    for i, (
        tp,
        alight_station,
        _alight_system,
        board_station,
        _board_system,
    ) in enumerate(oriented_transfers):
        responses = leg_responses.get(i, {})
        leg1_response = responses.get("leg1")
        leg2_response = responses.get("leg2")
        if not leg1_response or not leg1_response.departures:
            continue
        if not leg2_response or not leg2_response.departures:
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

    transfer_trips = _filter_unreasonable_durations(transfer_trips)

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
