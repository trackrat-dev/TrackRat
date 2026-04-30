"""
Metra unified collector for train discovery and journey updates.

Uses the MetraClient to fetch GTFS-RT data and creates/updates TrainJourney records.
Follows the same pattern as the LIRR collector.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.metra.client import MetraArrival, MetraClient, MetraFetchError
from trackrat.collectors.mta_common import (
    JOURNEY_UPDATE_LOAD_OPTIONS,
    ORIGIN_TRAVEL_BUFFER,
    build_complete_stops,
    check_journey_completed,
    infer_missing_origin,
    select_matching_trip,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.config.stations import (
    get_station_name,
)
from trackrat.config.stations.metra import (
    METRA_ROUTES,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_for_provider

logger = logging.getLogger(__name__)

DATA_SOURCE = "METRA"

# Module-level counter that persists across collector instantiations (same process).
# Reset on any successful non-empty fetch.
_consecutive_empty_cycles = 0
_CONSECUTIVE_EMPTY_THRESHOLD = 3


def _generate_train_id(trip_id: str) -> str:
    """
    Generate a stable train ID for Metra trains.

    Metra GTFS trip_ids follow the format: "{route}_{train_number}_{date}_{variant}"
    e.g., "ME_ME2012_V1_B" or "BNSF_BNSF1234_V1_A"

    We extract the train number portion and prefix with "MT".
    """
    parts = trip_id.split("_")
    if len(parts) >= 2:
        # Second segment is typically the train number with route prefix
        # e.g., "ME2012" from "ME_ME2012_V1_B"
        train_number = parts[1]
        # Strip the route prefix if it's duplicated (e.g., "ME2012" -> "2012")
        route_prefix = parts[0]
        if train_number.startswith(route_prefix):
            train_number = train_number[len(route_prefix) :]
        if train_number:
            return f"MT{train_number}"

    # Fallback: extract digits
    logger.warning("Unexpected Metra trip_id format: %s", trip_id)
    digits = "".join(c for c in trip_id if c.isdigit())[-6:]
    return f"MT{digits or trip_id[:6]}"


class MetraCollector:
    """
    Unified Metra collector that discovers trains and updates journeys.

    Polls the GTFS-RT feed every collection cycle to:
    1. Discover new trains (create TrainJourney records)
    2. Update existing trains with real-time data (delays, stops)

    Same pattern as LIRRCollector.
    """

    def __init__(self, client: MetraClient | None = None) -> None:
        """Initialize collector.

        Args:
            client: Optional MetraClient instance. Creates new one if not provided.
        """
        self.client = client or MetraClient()
        self._owns_client = client is None
        self._gtfs_service = GTFSService()

    async def run(self) -> dict[str, Any]:
        """
        Main entry point for the collector.

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
        Collect Metra train data.

        Args:
            session: Database session

        Returns:
            Statistics dict
        """
        global _consecutive_empty_cycles

        stats = {
            "discovered": 0,
            "updated": 0,
            "expired": 0,
            "errors": 0,
            "total_arrivals": 0,
        }

        if not self.client.has_credentials:
            raise RuntimeError(
                "Metra collection failed: API credentials not configured"
            )

        try:
            collection_start = now_for_provider(DATA_SOURCE)

            # Fetch all arrivals — let MetraFetchError propagate
            try:
                arrivals = await self.client.get_all_arrivals()
            except MetraFetchError as e:
                _consecutive_empty_cycles = 0
                raise RuntimeError(f"Metra feed fetch failed: {e}") from e

            stats["total_arrivals"] = len(arrivals)

            if not arrivals:
                _consecutive_empty_cycles += 1
                if _consecutive_empty_cycles >= _CONSECUTIVE_EMPTY_THRESHOLD:
                    raise RuntimeError(
                        f"Metra collection: {_consecutive_empty_cycles} consecutive "
                        f"cycles returned 0 arrivals — possible auth or API failure "
                        f"(auth_method={self.client._auth_method})"
                    )
                logger.warning(
                    "metra_empty_feed",
                    extra={
                        "consecutive_empty_cycles": _consecutive_empty_cycles,
                        "threshold": _CONSECUTIVE_EMPTY_THRESHOLD,
                    },
                )
                return stats

            # Successful non-empty fetch — reset the counter
            _consecutive_empty_cycles = 0

            # Group arrivals by trip_id
            trips: dict[str, list[MetraArrival]] = {}
            for arrival in arrivals:
                if arrival.trip_id not in trips:
                    trips[arrival.trip_id] = []
                trips[arrival.trip_id].append(arrival)

            logger.info(f"Found {len(trips)} Metra trips in GTFS-RT feed")

            # Process each trip inside a savepoint, committing in batches
            # to preserve partial progress on timeout or late-stage failure.
            batch_size = 50
            trips_in_batch = 0
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
                    logger.error(f"Error processing Metra trip {trip_id}: {e}")
                    stats["errors"] += 1

                trips_in_batch += 1
                if trips_in_batch >= batch_size:
                    await session.commit()
                    trips_in_batch = 0

            # If every trip failed, raise so scheduler marks this run as failed
            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"Metra collection: all {stats['errors']} trips failed, "
                    f"no successful discoveries or updates"
                )

            # Expire active OBSERVED journeys not seen in this collection cycle
            today = collection_start.date()
            stale_result = await session.execute(
                select(TrainJourney).where(
                    TrainJourney.data_source == DATA_SOURCE,
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
                        f"Metra journey expired: {journey.train_id} "
                        f"(error_count={journey.api_error_count})"
                    )

            await session.commit()
            logger.info(
                f"Metra collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Metra collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip_id: str, arrivals: list[MetraArrival]
    ) -> str | None:
        """
        Process a single trip from the GTFS-RT feed.

        Creates a new TrainJourney if this trip doesn't exist,
        or updates the existing one with new stop times.

        Args:
            session: Database session
            trip_id: GTFS trip_id
            arrivals: List of arrivals for this trip

        Returns:
            "discovered", "updated", or None
        """
        if not arrivals:
            return None

        # Sort arrivals by time to get stop sequence
        arrivals.sort(key=lambda a: a.arrival_time)

        first_arrival = arrivals[0]
        last_arrival = arrivals[-1]
        route_id = first_arrival.route_id

        # Get route info
        route_info = METRA_ROUTES.get(route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"METRA-{route_id}"
            line_name = f"Metra {route_id}"
            line_color = "#00558A"  # Default Metra blue

        # Determine origin and destination
        origin_code = first_arrival.station_code
        terminal_code = last_arrival.station_code

        # Generate train ID
        train_id = _generate_train_id(trip_id)

        # Determine journey date in Central Time
        from trackrat.utils.time import PROVIDER_TIMEZONE

        ct = PROVIDER_TIMEZONE[DATA_SOURCE]
        arrival_ct = first_arrival.arrival_time.astimezone(ct)
        journey_date = arrival_ct.date()

        # Check if journey already exists
        existing = await session.execute(
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == DATA_SOURCE,
            )
            .options(*JOURNEY_UPDATE_LOAD_OPTIONS)
        )
        journey = existing.scalar_one_or_none()

        if journey is None:
            # Backfill missing stops from GTFS static
            static_stops = await self._gtfs_service.get_static_stop_times(
                session, DATA_SOURCE, trip_id, journey_date
            )
            if static_stops:
                merged_stops, origin_code, terminal_code = build_complete_stops(
                    arrivals, static_stops
                )
                if not merged_stops:
                    logger.warning(
                        "Metra GTFS static backfill returned no usable stops "
                        "for trip %s; falling back to RT-only stops",
                        trip_id,
                    )
            else:
                merged_stops = None
                logger.warning(
                    "Metra GTFS static backfill unavailable for trip %s; "
                    "falling back to RT-only stops",
                    trip_id,
                )

            # Infer origin for outbound trains whose origin was dropped from RT
            inferred_origin: str | None = None
            if not merged_stops:
                inferred_origin = infer_missing_origin(
                    first_arrival.station_code, first_arrival.direction_id, DATA_SOURCE
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
                    "Skipping Metra trip %s: only %d usable stop(s)",
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
                data_source=DATA_SOURCE,
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
                # Synthesize a departed origin stop when origin was dropped
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
            now = now_for_provider(DATA_SOURCE)
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now, created_stops)
            check_journey_completed(journey, created_stops)

            # Analyze segments for congestion data
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments(session, journey)

            logger.debug(f"Discovered Metra train {train_id}")
            return "discovered"

        else:
            # Update existing journey
            journey.actual_departure = first_arrival.arrival_time
            journey.actual_arrival = last_arrival.arrival_time

            # Update stops
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

            # Update departure status and journey metadata
            now = now_for_provider(DATA_SOURCE)
            stop_result = await session.execute(
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence)
            )
            journey_stops = list(stop_result.scalars().all())
            update_stop_departure_status(journey_stops, now)
            update_journey_metadata(journey, now, journey_stops)
            check_journey_completed(journey, journey_stops)

            # Analyze segments for congestion data
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments(session, journey)

            logger.debug(f"Updated Metra train {train_id}")
            return "updated"

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
        if journey.data_source != DATA_SOURCE:
            return

        try:
            arrivals = await self.client.get_all_arrivals()
        except MetraFetchError:
            logger.warning(
                "metra_jit_fetch_failed", extra={"train_id": journey.train_id}
            )
            return

        journey_station_codes = {s.station_code for s in journey.stops}

        # Find arrivals that might be part of this journey
        matching_trips: dict[str, list[MetraArrival]] = {}
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
            DATA_SOURCE,
        )

        if not best_trip:
            logger.debug(f"No matching Metra trip found for journey {journey.train_id}")
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

        # Update journey-level times
        first_stop = min(best_trip, key=lambda a: a.arrival_time)
        last_stop = max(best_trip, key=lambda a: a.arrival_time)

        journey.actual_departure = first_stop.arrival_time
        journey.actual_arrival = last_stop.arrival_time

        # Update departure status and journey metadata
        now = now_for_provider(DATA_SOURCE)
        stop_result = await session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        journey_stops = list(stop_result.scalars().all())
        update_stop_departure_status(journey_stops, now)
        update_journey_metadata(journey, now, journey_stops)
        check_journey_completed(journey, journey_stops)

        logger.debug(f"JIT updated Metra journey {journey.train_id}")

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
