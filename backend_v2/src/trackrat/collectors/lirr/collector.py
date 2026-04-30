"""
LIRR unified collector for train discovery and journey updates.

Uses the LIRRClient to fetch GTFS-RT data and creates/updates TrainJourney records.
Follows the same pattern as the PATH collector for simplicity.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.lirr.client import LirrArrival, LIRRClient
from trackrat.collectors.mta_common import (
    JOURNEY_UPDATE_LOAD_OPTIONS,
    ORIGIN_TRAVEL_BUFFER,
    build_complete_stops,
    check_journey_completed,
    infer_missing_origin,
    select_matching_trip,
    set_stop_track,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.config.stations import (
    LIRR_ROUTES,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import ET, now_et

logger = logging.getLogger(__name__)

# Outer bound on the feed fetch. Generous relative to the per-phase timeouts in
# LIRRClient, but still leaves the bulk of the 480s scheduler budget for DB
# work when the upstream MTA endpoint is degraded.
_FEED_FETCH_TIMEOUT_SECONDS = 60.0


def _generate_train_id(trip_id: str) -> str:
    """
    Generate a stable train ID for LIRR trains.

    LIRR GTFS trip_ids follow several formats:
    - GO-prefix:  "GO103_25_181"              -> train number is 3rd segment ("181")
    - GO-event:   "GO103_25_367_2891_METS"    -> train number is still 3rd segment ("367")
    - Date-suffix: "7597_2026-02-22"          -> train number is 1st segment ("7597")

    The "L" prefix ensures LIRR trains are displayed as "L181" etc.
    """
    parts = trip_id.split("_")
    if len(parts) >= 3:
        train_number = parts[2]
    elif len(parts) == 2 and "-" in parts[1]:
        # Date-suffix format: "{train_number}_{YYYY-MM-DD}"
        train_number = parts[0]
    else:
        # Fallback for unexpected formats: extract digits from end
        logger.warning("Unexpected LIRR trip_id format: %s", trip_id)
        train_number = "".join(c for c in trip_id if c.isdigit())[-6:]

    if not train_number:
        train_number = trip_id[:6]

    return f"L{train_number}"


class LIRRCollector:
    """
    Unified LIRR collector that discovers trains and updates journeys.

    Polls the GTFS-RT feed every collection cycle to:
    1. Discover new trains (create TrainJourney records)
    2. Update existing trains with real-time data (delays, stops)

    Similar to PATH's unified collector pattern.
    """

    def __init__(self, client: LIRRClient | None = None) -> None:
        """Initialize collector.

        Args:
            client: Optional LIRRClient instance. Creates new one if not provided.
        """
        self.client = client or LIRRClient()
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
        Collect LIRR train data.

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

            # Fetch all arrivals. Wrap in wait_for so an upstream MTA outage
            # (hung connects, stalled reads beyond the phase timeouts) can't
            # consume the whole 480s scheduler budget — we bail with empty
            # stats and pick it up next cycle (~4 min).
            try:
                arrivals = await asyncio.wait_for(
                    self.client.get_all_arrivals(),
                    timeout=_FEED_FETCH_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "lirr_feed_fetch_timed_out | timeout_s=%.1f",
                    _FEED_FETCH_TIMEOUT_SECONDS,
                )
                return stats

            stats["total_arrivals"] = len(arrivals)

            if not arrivals:
                logger.warning("No LIRR arrivals found in GTFS-RT feed")
                return stats

            # Group arrivals by trip_id
            trips: dict[str, list[LirrArrival]] = {}
            for arrival in arrivals:
                if arrival.trip_id not in trips:
                    trips[arrival.trip_id] = []
                trips[arrival.trip_id].append(arrival)

            logger.info(f"Found {len(trips)} LIRR trips in GTFS-RT feed")

            # Process each trip inside a savepoint, committing in batches
            # to preserve partial progress on timeout or late-stage failure.
            batch_size = 50
            trips_in_batch = 0
            analyzed_journeys: list[TrainJourney] = []
            for trip_id, trip_arrivals in trips.items():
                try:
                    async with session.begin_nested():
                        result, journey = await self._process_trip(
                            session, trip_id, trip_arrivals
                        )
                        if result == "discovered":
                            stats["discovered"] += 1
                        elif result == "updated":
                            stats["updated"] += 1
                        if journey is not None and journey.id is not None:
                            analyzed_journeys.append(journey)
                except Exception as e:
                    logger.error(f"Error processing LIRR trip {trip_id}: {e}")
                    stats["errors"] += 1

                trips_in_batch += 1
                if trips_in_batch >= batch_size:
                    await session.commit()
                    trips_in_batch = 0

            # If every trip failed, raise so scheduler marks this run as failed
            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"LIRR collection: all {stats['errors']} trips failed, "
                    f"no successful discoveries or updates"
                )

            # Batched segment analysis for all processed journeys. Moving this
            # out of the per-trip loop eliminates the O(trips * stops)
            # per-segment SELECTs that dominate per-cycle cost.
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments_bulk(session, analyzed_journeys)

            # Expire active OBSERVED journeys not seen in this collection cycle.
            # Processed journeys have last_updated_at >= collection_start;
            # unseen ones retain their older timestamp.
            today = collection_start.date()
            stale_result = await session.execute(
                select(TrainJourney).where(
                    TrainJourney.data_source == "LIRR",
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
                        f"LIRR journey expired: {journey.train_id} "
                        f"(error_count={journey.api_error_count})"
                    )

            await session.commit()
            logger.info(
                f"LIRR collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"LIRR collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip_id: str, arrivals: list[LirrArrival]
    ) -> tuple[str | None, TrainJourney | None]:
        """
        Process a single trip from the GTFS-RT feed.

        Creates a new TrainJourney if this trip doesn't exist,
        or updates the existing one with new stop times.

        Args:
            session: Database session
            trip_id: GTFS trip_id
            arrivals: List of arrivals for this trip

        Returns:
            Tuple of (result_type, journey) where result_type is
            "discovered", "updated", or None. The journey reference is
            returned so the caller can batch post-processing (e.g.,
            TransitAnalyzer) after the per-trip loop completes.
        """
        if not arrivals:
            return None, None

        # Sort arrivals by time to get stop sequence
        arrivals.sort(key=lambda a: a.arrival_time)

        # Get trip info from first arrival
        first_arrival = arrivals[0]
        last_arrival = arrivals[-1]
        route_id = first_arrival.route_id

        # Get route info
        route_info = LIRR_ROUTES.get(route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"LIRR-{route_id}"
            line_name = f"LIRR Route {route_id}"
            line_color = "#0039A6"  # Default LIRR blue

        # Determine origin and destination
        origin_code = first_arrival.station_code
        terminal_code = last_arrival.station_code

        # Generate train ID
        train_id = _generate_train_id(trip_id)

        # Determine journey date (in Eastern time)
        # Use the departure time from origin, converted to ET for correct date
        arrival_et = first_arrival.arrival_time.astimezone(ET)
        journey_date = arrival_et.date()

        # Check if journey already exists
        existing = await session.execute(
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == "LIRR",
            )
            .options(*JOURNEY_UPDATE_LOAD_OPTIONS)
        )
        journey = existing.scalar_one_or_none()

        if journey is None:
            # Backfill missing stops from GTFS static (e.g., LIRR RT feed
            # drops origin terminal from outbound trips)
            static_stops = await self._gtfs_service.get_static_stop_times(
                session, "LIRR", trip_id, journey_date
            )
            if static_stops:
                merged_stops, origin_code, terminal_code = build_complete_stops(
                    arrivals, static_stops
                )
                if not merged_stops:
                    # All static stops had unmapped station codes
                    logger.warning(
                        "LIRR GTFS static backfill returned no usable stops "
                        "for trip %s; falling back to RT-only stops",
                        trip_id,
                    )
            else:
                merged_stops = None
                logger.warning(
                    "LIRR GTFS static backfill unavailable for trip %s; "
                    "falling back to RT-only stops",
                    trip_id,
                )

            # When GTFS backfill produced no usable stops, infer origin
            # for outbound trains whose origin terminal was dropped from RT
            inferred_origin: str | None = None
            if not merged_stops:
                inferred_origin = infer_missing_origin(
                    first_arrival.station_code, first_arrival.direction_id, "LIRR"
                )
                if inferred_origin:
                    origin_code = inferred_origin

            # Skip trips with fewer than 2 usable stops when no static
            # backfill is available.  LIRR GTFS-RT includes future trains
            # where only the origin terminal has a departure time; creating
            # a 1-stop journey with origin == destination is nonsensical.
            effective_stop_count = (
                len(merged_stops)
                if merged_stops
                else len(arrivals) + (1 if inferred_origin else 0)
            )
            if effective_stop_count < 2:
                logger.debug(
                    "Skipping LIRR trip %s: only %d usable stop(s)",
                    trip_id,
                    effective_stop_count,
                )
                return None, None

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
                data_source="LIRR",
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

            # Create stops — collect into local list to avoid lazy-loading
            # journey.stops in async context (MissingGreenlet)
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
                # Synthesize a departed origin stop when the origin terminal
                # was dropped from GTFS-RT and static backfill is unavailable
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

            # Infer departure status for trains discovered mid-journey
            await session.flush()
            now = now_et()
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now, created_stops)
            check_journey_completed(journey, created_stops)

            logger.debug(f"Discovered LIRR train {train_id}")
            return "discovered", journey

        else:
            # Update existing journey — arrival_time is already the predicted time
            journey.actual_departure = first_arrival.arrival_time
            journey.actual_arrival = last_arrival.arrival_time

            # Use in-memory lookup from eagerly-loaded stops (avoids N+1 queries).
            # journey.stops was loaded via selectinload on the existence check above.
            stops_by_code = {s.station_code: s for s in journey.stops}
            for arr in arrivals:
                existing_stop = stops_by_code.get(arr.station_code)

                if existing_stop:
                    existing_stop.actual_arrival = arr.arrival_time
                    existing_stop.updated_arrival = arr.arrival_time
                    existing_stop.arrival_source = "api_observed"
                    if arr.departure_time:
                        existing_stop.actual_departure = arr.departure_time
                        existing_stop.updated_departure = arr.departure_time
                    set_stop_track(
                        existing_stop, arr.track, "LIRR", journey.train_id, now_et()
                    )

            # Update departure status and journey metadata using the in-memory
            # stops collection — no re-query needed.
            now = now_et()
            journey_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
            update_stop_departure_status(journey_stops, now)
            update_journey_metadata(journey, now, journey_stops)
            check_journey_completed(journey, journey_stops)

            logger.debug(f"Updated LIRR train {train_id}")
            return "updated", journey

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """
        JIT update for a single journey.

        Called by DepartureService when a journey's data is stale.

        Args:
            session: Database session
            journey: TrainJourney to update
        """
        if journey.data_source != "LIRR":
            return

        # Fetch latest arrivals for all stops of this journey
        arrivals = await self.client.get_all_arrivals()

        # Find arrivals that match this journey's stops
        journey_station_codes = {s.station_code for s in journey.stops}

        # Find arrivals that might be part of this journey
        # Match by origin station and approximate departure time
        matching_trips: dict[str, list[LirrArrival]] = {}

        for arr in arrivals:
            if arr.station_code not in journey_station_codes:
                continue
            if arr.trip_id not in matching_trips:
                matching_trips[arr.trip_id] = []
            matching_trips[arr.trip_id].append(arr)

        best_trip = select_matching_trip(
            matching_trips,
            journey,
            journey_station_codes,
            _generate_train_id,
            "LIRR",
        )

        if not best_trip:
            logger.debug(f"No matching LIRR trip found for journey {journey.train_id}")
            return

        # Update journey with latest data
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
                set_stop_track(stop, arr.track, "LIRR", journey.train_id, now_et())

        # Update journey-level times — arrival_time is already the predicted time
        first_stop = min(best_trip, key=lambda a: a.arrival_time)
        last_stop = max(best_trip, key=lambda a: a.arrival_time)

        journey.actual_departure = first_stop.arrival_time
        journey.actual_arrival = last_stop.arrival_time

        # Update departure status and journey metadata
        now = now_et()
        stop_result = await session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        journey_stops = list(stop_result.scalars().all())
        update_stop_departure_status(journey_stops, now)
        update_journey_metadata(journey, now, journey_stops)
        check_journey_completed(journey, journey_stops)

        logger.debug(f"JIT updated LIRR journey {journey.train_id}")

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
