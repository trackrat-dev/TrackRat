"""
NYC Subway unified collector for train discovery and journey updates.

Uses the SubwayClient to fetch GTFS-RT data from all 8 feeds and creates/updates
TrainJourney records. Follows the same pattern as the LIRR/MNR collectors.

Key differences from LIRR/MNR:
- Uses NYCT train_id extension for stable train identification
- Full-replacement feed semantics: trains not in current feed are expired
  immediately (no 3-strike rule) since subway feeds are complete snapshots
- 8 feeds fetched concurrently via SubwayClient
"""

import hashlib
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trackrat.collectors.mta_common import (
    ORIGIN_TRAVEL_BUFFER,
    build_complete_stops,
    check_journey_completed,
    infer_missing_origin,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.collectors.subway.client import SubwayArrival, SubwayClient, _ROUTE_TO_FEED
from trackrat.config.stations import (
    SUBWAY_ROUTES,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import ET, now_et

logger = logging.getLogger(__name__)

# Subway full-replacement window: if a journey was updated within this
# window but is missing from the current feed, expire it immediately.
_REPLACEMENT_WINDOW = timedelta(minutes=30)


def _generate_train_id(trip_id: str, nyct_train_id: str | None, route_id: str) -> str:
    """
    Generate a stable train ID for subway trains.

    Prefers the NYCT train_id from the protobuf extension (e.g., "01 0123+ PEL/BBR").
    Falls back to a hash of the trip_id if extension is unavailable.

    The NYCT train_id format includes a 2-digit origin time code followed by a 4-digit
    train number. We use all digits to avoid collisions between trains that share the
    same 4-digit number but differ in origin time. Produces IDs like "S6-010123".
    """
    if nyct_train_id:
        # Extract all digits from NYCT train_id (e.g., "01 0123+ PEL/BBR" -> "010123")
        digits = "".join(c for c in nyct_train_id if c.isdigit())
        if digits:
            return f"S{route_id}-{digits}"

    # Fallback: hash trip_id to 6-char hex
    h = hashlib.md5(trip_id.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"S{route_id}-{h}"


class SubwayCollector:
    """
    Unified NYC Subway collector that discovers trains and updates journeys.

    Polls all 8 GTFS-RT feeds every collection cycle to:
    1. Discover new trains (create TrainJourney records)
    2. Update existing trains with real-time data (delays, stops)
    3. Expire trains no longer in the feed (full-replacement semantics)
    """

    def __init__(self, client: SubwayClient | None = None) -> None:
        self.client = client or SubwayClient()
        self._owns_client = client is None
        self._gtfs_service = GTFSService()

    async def run(self) -> dict[str, Any]:
        """Main entry point. Creates a database session and runs collection."""
        async with get_session() as session:
            return await self.collect(session)

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """
        Collect NYC Subway train data.

        1. Fetch all arrivals from all 8 GTFS-RT feeds concurrently
        2. Group by trip_id to identify unique trains
        3. For each train, create or update TrainJourney record
        4. Expire journeys not seen in this feed (full-replacement)
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

            # Fetch all arrivals from all 8 feeds
            arrivals, succeeded_feeds = await self.client.get_all_arrivals()
            stats["total_arrivals"] = len(arrivals)

            if not arrivals:
                logger.warning("No subway arrivals found in GTFS-RT feeds")
                return stats

            # Group arrivals by trip_id
            trips: dict[str, list[SubwayArrival]] = {}
            for arrival in arrivals:
                if arrival.trip_id not in trips:
                    trips[arrival.trip_id] = []
                trips[arrival.trip_id].append(arrival)

            logger.info(f"Found {len(trips)} subway trips in GTFS-RT feeds")

            # Process each trip inside a savepoint
            seen_journey_ids: set[int] = set()
            for trip_id, trip_arrivals in trips.items():
                try:
                    async with session.begin_nested():
                        result, journey_id = await self._process_trip(
                            session, trip_id, trip_arrivals
                        )
                        if result == "discovered":
                            stats["discovered"] += 1
                        elif result == "updated":
                            stats["updated"] += 1
                        if journey_id:
                            seen_journey_ids.add(journey_id)
                except Exception as e:
                    logger.error(f"Error processing subway trip {trip_id}: {e}")
                    stats["errors"] += 1

            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"Subway collection: all {stats['errors']} trips failed"
                )

            # Full-replacement expiration: subway feeds are complete snapshots,
            # so any active journey NOT in the current feed should be expired
            # immediately (unlike LIRR/MNR which use 3-strike rule).
            today = collection_start.date()
            stale_result = await session.execute(
                select(TrainJourney).where(
                    TrainJourney.data_source == "SUBWAY",
                    TrainJourney.observation_type == "OBSERVED",
                    TrainJourney.journey_date >= today - timedelta(days=1),
                    TrainJourney.is_completed == False,  # noqa: E712
                    TrainJourney.is_expired == False,  # noqa: E712
                    TrainJourney.is_cancelled == False,  # noqa: E712
                    TrainJourney.last_updated_at < collection_start,
                )
            )
            for journey in stale_result.scalars():
                if journey.id in seen_journey_ids:
                    continue
                # Skip expiration for trains whose feed failed this cycle
                route_feed = _ROUTE_TO_FEED.get(journey.line_code or "")
                if route_feed and route_feed not in succeeded_feeds:
                    continue
                # Only expire if it was recently active (within replacement window)
                if journey.last_updated_at and (
                    collection_start - journey.last_updated_at.astimezone(ET)
                    < _REPLACEMENT_WINDOW
                ):
                    journey.is_expired = True
                    stats["expired"] += 1
                else:
                    # Old journeys: use standard 3-strike rule
                    journey.api_error_count = (journey.api_error_count or 0) + 1
                    if journey.api_error_count >= 3:
                        journey.is_expired = True
                        stats["expired"] += 1

            await session.commit()
            logger.info(
                f"Subway collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Subway collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip_id: str, arrivals: list[SubwayArrival]
    ) -> tuple[str | None, int | None]:
        """
        Process a single trip from the GTFS-RT feed.

        Returns:
            Tuple of (result_type, journey_id) where result_type is
            "discovered", "updated", or None
        """
        if not arrivals:
            return None, None

        arrivals.sort(key=lambda a: a.arrival_time)

        first_arrival = arrivals[0]
        last_arrival = arrivals[-1]
        route_id = first_arrival.route_id

        # Get route info
        route_info = SUBWAY_ROUTES.get(route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"SUBWAY-{route_id}"
            line_name = f"Subway {route_id}"
            line_color = "#0039A6"

        origin_code = first_arrival.station_code
        terminal_code = last_arrival.station_code

        # Generate train ID using NYCT extension
        train_id = _generate_train_id(trip_id, first_arrival.nyct_train_id, route_id)

        # Determine journey date in Eastern time
        arrival_et = first_arrival.arrival_time.astimezone(ET)
        journey_date = arrival_et.date()

        # Check if journey already exists
        existing = await session.execute(
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == "SUBWAY",
            )
            .options(selectinload(TrainJourney.stops))
        )
        journey = existing.scalar_one_or_none()

        if journey is None:
            # Try GTFS static backfill
            static_stops = await self._gtfs_service.get_static_stop_times(
                session, "SUBWAY", trip_id, journey_date
            )
            merged_stops = None
            if static_stops:
                merged_stops, origin_code, terminal_code = build_complete_stops(
                    arrivals, static_stops
                )
                if not merged_stops:
                    logger.debug(
                        "Subway GTFS backfill returned no usable stops for trip %s",
                        trip_id,
                    )

            inferred_origin: str | None = None
            if not merged_stops:
                inferred_origin = infer_missing_origin(
                    first_arrival.station_code, first_arrival.direction_id, "SUBWAY"
                )
                if inferred_origin:
                    origin_code = inferred_origin

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

            journey = TrainJourney(
                train_id=train_id,
                journey_date=journey_date,
                data_source="SUBWAY",
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
                        track=stop_data["track"],
                        has_departed_station=stop_data["has_departed"],
                    )
                    session.add(stop)
                    created_stops.append(stop)
            else:
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
                        track=None,
                        has_departed_station=True,
                        departure_source="synthetic_origin",
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
                        track=arr.track,
                        has_departed_station=False,
                    )
                    session.add(stop)
                    created_stops.append(stop)
                    seq += 1

            await session.flush()
            now = now_et()
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now)
            check_journey_completed(journey, created_stops)

            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments(session, journey)

            logger.debug(f"Discovered subway train {train_id}")
            return "discovered", journey.id

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
                    if arr.departure_time:
                        existing_stop.actual_departure = arr.departure_time
                    if arr.track:
                        existing_stop.track = arr.track

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

            logger.debug(f"Updated subway train {train_id}")
            return "updated", journey.id

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """JIT update for a single journey."""
        if journey.data_source != "SUBWAY":
            return

        # Fetch only the relevant feed based on route, not all 8
        arrivals = await self.client.get_feed_arrivals(journey.line_code or "")

        journey_station_codes = {s.station_code for s in journey.stops}
        matching_trips: dict[str, list[SubwayArrival]] = {}

        for arr in arrivals:
            if arr.station_code not in journey_station_codes:
                continue
            if arr.trip_id not in matching_trips:
                matching_trips[arr.trip_id] = []
            matching_trips[arr.trip_id].append(arr)

        best_trip: list[SubwayArrival] | None = None
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
            logger.debug(
                f"No matching subway trip found for journey {journey.train_id}"
            )
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
                if arr.departure_time:
                    stop.actual_departure = arr.departure_time
                if arr.track:
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

        logger.debug(f"JIT updated subway journey {journey.train_id}")

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
