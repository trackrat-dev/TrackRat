"""
MBTA unified collector for Commuter Rail train discovery and journey updates.

Uses the MBTAClient to fetch GTFS-RT data and creates/updates TrainJourney records.
Follows the same pattern as the LIRR collector.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trackrat.collectors.mbta.client import MbtaArrival, MBTAClient
from trackrat.collectors.mta_common import (
    ORIGIN_TRAVEL_BUFFER,
    build_complete_stops,
    check_journey_completed,
    infer_missing_origin,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.config.stations import (
    MBTA_ROUTES,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import ET, now_et

logger = logging.getLogger(__name__)


def _generate_train_id(trip_id: str) -> str:
    """
    Generate a stable train ID for MBTA trains.

    MBTA GTFS trip_ids follow formats like:
    - "Base-772221-5208"                    -> train number is "5208"
    - "OCTieJob-791415-6619"                -> train number is "6619"
    - "SouthWKNDBase25-772583-6619"         -> train number is "6619"
    - "canonical-CapeFlyer-C1-0"            -> use "CF-C1"

    The train number is the trip_short_name in GTFS, which is the last
    numeric segment in the trip_id. The "B" prefix ensures MBTA trains
    are displayed as "B5208" etc.
    """
    parts = trip_id.split("-")

    # CapeFlyer format: "canonical-CapeFlyer-C1-0"
    if "CapeFlyer" in trip_id:
        for p in parts:
            if p.startswith("C") and len(p) <= 3:
                return f"BCF-{p}"
        return f"BCF-{parts[-1]}"

    # Standard CR format: "{prefix}-{number}-{train_number}"
    # The train number is always the last segment
    last_segment = parts[-1]
    if last_segment.isdigit():
        return f"B{last_segment}"

    # Fallback: extract digits from the trip_id
    digits = "".join(c for c in trip_id if c.isdigit())
    if digits:
        return f"B{digits[-6:]}"

    logger.warning("Unexpected MBTA trip_id format: %s", trip_id)
    return f"B{trip_id[:8]}"


class MBTACollector:
    """
    Unified MBTA Commuter Rail collector that discovers trains and updates journeys.

    Polls the GTFS-RT feed every collection cycle to:
    1. Discover new trains (create TrainJourney records)
    2. Update existing trains with real-time data (delays, stops)
    """

    def __init__(self, client: MBTAClient | None = None) -> None:
        """Initialize collector.

        Args:
            client: Optional MBTAClient instance. Creates new one if not provided.
        """
        self.client = client or MBTAClient()
        self._owns_client = client is None
        self._gtfs_service = GTFSService()

    async def run(self) -> dict[str, Any]:
        """
        Main entry point for the collector.

        Creates a database session and runs collection.

        Returns:
            Statistics dict with discovery/update counts
        """
        try:
            async with get_session() as session:
                return await self.collect(session)
        finally:
            if self._owns_client:
                await self.client.close()

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """
        Collect MBTA Commuter Rail train data.

        1. Fetch all arrivals from GTFS-RT feed
        2. Group by trip_id to identify unique trains
        3. For each train, create or update TrainJourney record

        Args:
            session: Database session

        Returns:
            Statistics dict
        """
        stats = {
            "discovered": 0,
            "updated": 0,
            "expired": 0,
            "errors": 0,
            "total_arrivals": 0,
        }

        try:
            collection_start = now_et()

            # Fetch all arrivals
            arrivals = await self.client.get_all_arrivals()
            stats["total_arrivals"] = len(arrivals)

            if not arrivals:
                logger.warning("No MBTA CR arrivals found in GTFS-RT feed")
                return stats

            # Group arrivals by trip_id
            trips: dict[str, list[MbtaArrival]] = {}
            for arrival in arrivals:
                if arrival.trip_id not in trips:
                    trips[arrival.trip_id] = []
                trips[arrival.trip_id].append(arrival)

            logger.info(f"Found {len(trips)} MBTA CR trips in GTFS-RT feed")

            # Process each trip inside a savepoint
            for trip_id, trip_arrivals in trips.items():
                try:
                    async with session.begin_nested():
                        result = await self._process_trip(
                            session, trip_id, trip_arrivals
                        )
                        if result == "discovered":
                            stats["discovered"] += 1
                        elif result == "updated":
                            stats["updated"] += 1
                except Exception as e:
                    logger.error(f"Error processing MBTA trip {trip_id}: {e}")
                    stats["errors"] += 1

            # If every trip failed, raise so scheduler marks this run as failed
            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"MBTA collection: all {stats['errors']} trips failed, "
                    f"no successful discoveries or updates"
                )

            # Expire active OBSERVED journeys not seen in this collection cycle
            today = collection_start.date()
            stale_result = await session.execute(
                select(TrainJourney).where(
                    TrainJourney.data_source == "MBTA",
                    TrainJourney.observation_type == "OBSERVED",
                    TrainJourney.journey_date >= today - timedelta(days=1),
                    TrainJourney.is_completed == False,  # noqa: E712
                    TrainJourney.is_expired == False,  # noqa: E712
                    TrainJourney.is_cancelled == False,  # noqa: E712
                    TrainJourney.last_updated_at < collection_start,
                )
            )
            for journey in stale_result.scalars():
                journey.api_error_count = (journey.api_error_count or 0) + 1
                if journey.api_error_count >= 3:
                    journey.is_expired = True
                    stats["expired"] += 1
                    logger.info(
                        f"MBTA journey expired: {journey.train_id} "
                        f"(error_count={journey.api_error_count})"
                    )

            await session.commit()
            logger.info(
                f"MBTA collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"MBTA collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip_id: str, arrivals: list[MbtaArrival]
    ) -> str | None:
        """
        Process a single trip from the GTFS-RT feed.

        Creates a new TrainJourney if this trip doesn't exist,
        or updates the existing one with new stop times.
        """
        if not arrivals:
            return None

        # Sort arrivals by time
        arrivals.sort(key=lambda a: a.arrival_time)

        first_arrival = arrivals[0]
        last_arrival = arrivals[-1]
        route_id = first_arrival.route_id

        # Get route info
        route_info = MBTA_ROUTES.get(route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"MBTA-{route_id}"
            line_name = f"MBTA {route_id}"
            line_color = "#80276C"  # Default MBTA CR purple

        origin_code = first_arrival.station_code
        terminal_code = last_arrival.station_code

        # Generate train ID
        train_id = _generate_train_id(trip_id)

        # Determine journey date in Eastern time
        arrival_et = first_arrival.arrival_time.astimezone(ET)
        journey_date = arrival_et.date()

        # Check if journey already exists
        existing = await session.execute(
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == "MBTA",
            )
            .options(
                selectinload(TrainJourney.stops),
                # Load all delete-orphan collections to prevent
                # greenlet_spawn errors during flush orphan checks
                selectinload(TrainJourney.snapshots),
                selectinload(TrainJourney.segment_times),
                selectinload(TrainJourney.dwell_times),
                selectinload(TrainJourney.progress),
                selectinload(TrainJourney.progress_snapshots),
            )
        )
        journey = existing.scalar_one_or_none()

        if journey is None:
            # Try GTFS static backfill
            static_stops = await self._gtfs_service.get_static_stop_times(
                session, "MBTA", trip_id, journey_date
            )
            if static_stops:
                merged_stops, origin_code, terminal_code = build_complete_stops(
                    arrivals, static_stops
                )
                if not merged_stops:
                    logger.warning(
                        "MBTA GTFS static backfill returned no usable stops "
                        "for trip %s; falling back to RT-only stops",
                        trip_id,
                    )
            else:
                merged_stops = None
                logger.warning(
                    "MBTA GTFS static backfill unavailable for trip %s; "
                    "falling back to RT-only stops",
                    trip_id,
                )

            # Infer missing origin for outbound trains
            inferred_origin: str | None = None
            if not merged_stops:
                inferred_origin = infer_missing_origin(
                    first_arrival.station_code, first_arrival.direction_id, "MBTA"
                )
                if inferred_origin:
                    origin_code = inferred_origin

            # Skip trips with fewer than 2 usable stops
            effective_stop_count = (
                len(merged_stops)
                if merged_stops
                else len(arrivals) + (1 if inferred_origin else 0)
            )
            if effective_stop_count < 2:
                logger.debug(
                    "Skipping MBTA trip %s: only %d usable stop(s)",
                    trip_id,
                    effective_stop_count,
                )
                return None

            # Compute scheduled times
            if merged_stops:
                sched_departure = merged_stops[0]["scheduled_departure"]
                sched_arrival = merged_stops[-1]["scheduled_arrival"]
            else:
                first_delay = timedelta(seconds=first_arrival.delay_seconds)
                last_delay = timedelta(seconds=last_arrival.delay_seconds)
                first_sched = first_arrival.arrival_time - first_delay
                sched_departure = (
                    first_sched - ORIGIN_TRAVEL_BUFFER
                    if inferred_origin
                    else first_sched
                )
                sched_arrival = last_arrival.arrival_time - last_delay

            # Create new journey
            journey = TrainJourney(
                train_id=train_id,
                journey_date=journey_date,
                data_source="MBTA",
                observation_type="OBSERVED",
                line_code=line_code,
                line_name=line_name,
                line_color=line_color,
                destination=get_station_name(terminal_code),
                origin_station_code=origin_code,
                terminal_station_code=terminal_code,
                scheduled_departure=sched_departure,
                scheduled_arrival=sched_arrival,
                actual_departure=first_arrival.arrival_time,
                has_complete_journey=True,
                stops_count=(
                    len(merged_stops)
                    if merged_stops
                    else len(arrivals) + (1 if inferred_origin else 0)
                ),
                is_cancelled=False,
                is_completed=False,
                api_error_count=0,
                is_expired=False,
                discovery_station_code=first_arrival.station_code,
            )
            session.add(journey)
            await session.flush()

            # Create stops
            created_stops: list[JourneyStop] = []
            if merged_stops:
                for stop_data in merged_stops:
                    stop = JourneyStop(
                        journey_id=journey.id,
                        station_code=stop_data["station_code"],
                        station_name=get_station_name(stop_data["station_code"]),
                        stop_sequence=stop_data["stop_sequence"],
                        scheduled_arrival=stop_data["scheduled_arrival"],
                        scheduled_departure=stop_data["scheduled_departure"],
                        actual_arrival=stop_data["actual_arrival"],
                        actual_departure=stop_data["actual_departure"],
                        updated_arrival=stop_data["updated_arrival"],
                        updated_departure=stop_data["updated_departure"],
                        track=stop_data["track"],
                        has_departed_station=stop_data["has_departed"],
                        arrival_source=(
                            "api_observed" if stop_data["actual_arrival"] else None
                        ),
                    )
                    session.add(stop)
                    created_stops.append(stop)
            else:
                # Synthesize departed origin stop if needed
                if inferred_origin:
                    origin_actual = first_arrival.arrival_time - ORIGIN_TRAVEL_BUFFER
                    stop = JourneyStop(
                        journey_id=journey.id,
                        station_code=inferred_origin,
                        station_name=get_station_name(inferred_origin),
                        stop_sequence=1,
                        scheduled_arrival=sched_departure,
                        scheduled_departure=sched_departure,
                        actual_arrival=origin_actual,
                        actual_departure=origin_actual,
                        updated_arrival=origin_actual,
                        updated_departure=origin_actual,
                        track=None,
                        has_departed_station=True,
                        departure_source="synthetic_origin",
                        arrival_source="scheduled_fallback",
                    )
                    session.add(stop)
                    created_stops.append(stop)

                start_seq = 2 if inferred_origin else 1
                seen_codes: set[str] = set()
                if inferred_origin:
                    seen_codes.add(inferred_origin)
                seq = start_seq
                for arr in arrivals:
                    if arr.station_code in seen_codes:
                        continue
                    seen_codes.add(arr.station_code)
                    delay = timedelta(seconds=arr.delay_seconds)
                    stop = JourneyStop(
                        journey_id=journey.id,
                        station_code=arr.station_code,
                        station_name=get_station_name(arr.station_code),
                        stop_sequence=seq,
                        scheduled_arrival=arr.arrival_time - delay,
                        scheduled_departure=(
                            (arr.departure_time - delay)
                            if arr.departure_time
                            else (arr.arrival_time - delay)
                        ),
                        actual_arrival=arr.arrival_time,
                        actual_departure=arr.departure_time,
                        updated_arrival=arr.arrival_time,
                        updated_departure=arr.departure_time,
                        track=arr.track,
                        has_departed_station=False,
                        arrival_source="api_observed",
                    )
                    session.add(stop)
                    created_stops.append(stop)
                    seq += 1

            # Infer departure status
            await session.flush()
            now = now_et()
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now)
            check_journey_completed(journey, created_stops)

            # Analyze segments for congestion data
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments(session, journey)

            logger.debug(f"Discovered MBTA train {train_id}")
            return "discovered"

        else:
            # Update existing journey
            journey.actual_departure = first_arrival.arrival_time
            journey.actual_arrival = last_arrival.arrival_time

            for arr in arrivals:
                stop_result = await session.execute(
                    select(JourneyStop).where(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code == arr.station_code,
                    )
                )
                existing_stop = stop_result.scalar_one_or_none()

                if existing_stop:
                    existing_stop.actual_arrival = arr.arrival_time
                    existing_stop.updated_arrival = arr.arrival_time
                    existing_stop.arrival_source = "api_observed"
                    if arr.departure_time:
                        existing_stop.actual_departure = arr.departure_time
                        existing_stop.updated_departure = arr.departure_time
                    if arr.track:
                        if not existing_stop.track:
                            existing_stop.track_assigned_at = now_et()
                        existing_stop.track = arr.track

            # Update departure status and journey metadata
            now = now_et()
            stop_result = await session.execute(
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence)
            )
            journey_stops = list(stop_result.scalars().all())
            update_stop_departure_status(journey_stops, now)
            update_journey_metadata(journey, now)
            check_journey_completed(journey, journey_stops)

            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments(session, journey)

            logger.debug(f"Updated MBTA train {train_id}")
            return "updated"

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """
        JIT update for a single journey.

        Called by DepartureService when a journey's data is stale.
        """
        if journey.data_source != "MBTA":
            return

        arrivals = await self.client.get_all_arrivals()
        journey_station_codes = {s.station_code for s in journey.stops}

        matching_trips: dict[str, list[MbtaArrival]] = {}
        for arr in arrivals:
            if arr.station_code not in journey_station_codes:
                continue
            if arr.trip_id not in matching_trips:
                matching_trips[arr.trip_id] = []
            matching_trips[arr.trip_id].append(arr)

        # Exact match by train_id
        best_trip: list[MbtaArrival] | None = None
        for trip_id_candidate, trip_arrivals in matching_trips.items():
            if _generate_train_id(trip_id_candidate) == journey.train_id:
                best_trip = trip_arrivals
                break

        # Fuzzy fallback
        if best_trip is None:
            best_overlap = 0
            best_time_diff = float("inf")

            for trip_arrivals in matching_trips.values():
                trip_stations = {a.station_code for a in trip_arrivals}
                overlap = len(trip_stations & journey_station_codes)

                time_diff = float("inf")
                if journey.scheduled_departure:
                    first_arr = min(trip_arrivals, key=lambda a: a.arrival_time)
                    time_diff = abs(
                        (
                            first_arr.arrival_time - journey.scheduled_departure
                        ).total_seconds()
                    )

                if overlap > best_overlap or (
                    overlap == best_overlap and time_diff < best_time_diff
                ):
                    best_overlap = overlap
                    best_time_diff = time_diff
                    best_trip = trip_arrivals

        if not best_trip:
            logger.debug(f"No matching MBTA trip found for journey {journey.train_id}")
            return

        for arr in best_trip:
            stop_result = await session.execute(
                select(JourneyStop).where(
                    JourneyStop.journey_id == journey.id,
                    JourneyStop.station_code == arr.station_code,
                )
            )
            stop = stop_result.scalar_one_or_none()

            if stop:
                stop.actual_arrival = arr.arrival_time
                stop.updated_arrival = arr.arrival_time
                stop.arrival_source = "api_observed"
                if arr.departure_time:
                    stop.actual_departure = arr.departure_time
                    stop.updated_departure = arr.departure_time
                if arr.track:
                    if not stop.track:
                        stop.track_assigned_at = now_et()
                    stop.track = arr.track

        first_stop = min(best_trip, key=lambda a: a.arrival_time)
        last_stop = max(best_trip, key=lambda a: a.arrival_time)

        journey.actual_departure = first_stop.arrival_time
        journey.actual_arrival = last_stop.arrival_time

        now = now_et()
        stop_result = await session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        journey_stops = list(stop_result.scalars().all())
        update_stop_departure_status(journey_stops, now)
        update_journey_metadata(journey, now)
        check_journey_completed(journey, journey_stops)

        logger.debug(f"JIT updated MBTA journey {journey.train_id}")

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
