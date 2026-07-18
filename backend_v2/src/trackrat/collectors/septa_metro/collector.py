"""SEPTA Metro unified collector (subway + trolley).

Processes the Metro-filtered GTFS-RT feed and upserts TrainJourney records for
the lines SEPTA actually feeds in real time (today: Norristown HSL + trolleys).
Broad Street / Market-Frankford carry no real-time trips, so they never appear
here and are served schedule-only from GTFS static (like PATCO) — no special
casing required. When SEPTA starts feeding those lines, this collector begins
upgrading them to OBSERVED automatically.

Metro is frequency-first, so there is no origin inference (a line has two
terminals and the feed usually includes all remaining stops); GTFS static
backfills any passed stops when the trip is present in the schedule.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.mta_common import (
    JOURNEY_UPDATE_LOAD_OPTIONS,
    build_complete_stops,
    check_journey_completed,
    group_candidate_trips_by_overlap,
    select_matching_trip,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.collectors.septa_metro.client import SeptaMetroArrival, SeptaMetroClient
from trackrat.config.stations import get_septa_metro_route_info, get_station_name
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import ET, now_et

logger = logging.getLogger(__name__)

DATA_SOURCE = "SEPTA_METRO"
_DEFAULT_LINE_COLOR = "#4F758B"

_FEED_FETCH_TIMEOUT_SECONDS = 60.0


def _generate_train_id(trip_id: str) -> str:
    """Metro GTFS trip_ids are unique numeric ids; use them directly."""
    return trip_id


class SeptaMetroCollector:
    """Discovers SEPTA Metro trains and updates their journeys."""

    def __init__(self, client: SeptaMetroClient | None = None) -> None:
        self.client = client or SeptaMetroClient()
        self._owns_client = client is None
        self._gtfs_service = GTFSService()

    async def run(self) -> dict[str, Any]:
        try:
            async with get_session() as session:
                return await self.collect(session)
        finally:
            if self._owns_client:
                await self.client.close()

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        stats = {
            "discovered": 0,
            "updated": 0,
            "expired": 0,
            "errors": 0,
            "total_arrivals": 0,
        }

        try:
            collection_start = now_et()
            try:
                arrivals = await asyncio.wait_for(
                    self.client.get_all_arrivals(),
                    timeout=_FEED_FETCH_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "septa_metro_feed_fetch_timed_out | timeout_s=%.1f",
                    _FEED_FETCH_TIMEOUT_SECONDS,
                )
                return stats

            stats["total_arrivals"] = len(arrivals)
            if not arrivals:
                logger.warning("No SEPTA Metro arrivals found in GTFS-RT feed")
                return stats

            trips: dict[str, list[SeptaMetroArrival]] = {}
            for arrival in arrivals:
                trips.setdefault(arrival.trip_id, []).append(arrival)
            logger.info(f"Found {len(trips)} SEPTA Metro trips in GTFS-RT feed")

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
                    logger.error(f"Error processing SEPTA Metro trip {trip_id}: {e}")
                    stats["errors"] += 1

                trips_in_batch += 1
                if trips_in_batch >= batch_size:
                    await session.commit()
                    trips_in_batch = 0

            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"SEPTA Metro collection: all {stats['errors']} trips failed"
                )

            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_new_segments_bulk(session, analyzed_journeys)

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

            await session.commit()
            logger.info(
                f"SEPTA Metro collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )
        except Exception as e:
            logger.error(f"SEPTA Metro collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip_id: str, arrivals: list[SeptaMetroArrival]
    ) -> tuple[str | None, TrainJourney | None]:
        if not arrivals:
            return None, None

        arrivals.sort(key=lambda a: a.arrival_time)
        first_arrival = arrivals[0]
        last_arrival = arrivals[-1]
        route_id = first_arrival.route_id

        route_info = get_septa_metro_route_info(route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"SEPTA-{route_id}"
            line_name = f"SEPTA {route_id}"
            line_color = _DEFAULT_LINE_COLOR

        origin_code = first_arrival.station_code
        terminal_code = last_arrival.station_code
        train_id = _generate_train_id(trip_id)
        journey_date = first_arrival.arrival_time.astimezone(ET).date()

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
            static_stops = await self._gtfs_service.get_static_stop_times(
                session, DATA_SOURCE, trip_id, journey_date
            )
            merged_stops: list[dict[str, Any]] | None = None
            if static_stops:
                merged_stops, origin_code, terminal_code = build_complete_stops(
                    arrivals, static_stops
                )
                if not merged_stops:
                    merged_stops = None

            effective_stop_count = len(merged_stops) if merged_stops else len(arrivals)
            if effective_stop_count < 2:
                logger.debug(
                    "Skipping SEPTA Metro trip %s: only %d usable stop(s)",
                    trip_id,
                    effective_stop_count,
                )
                return None, None

            if merged_stops:
                sched_departure = merged_stops[0]["scheduled_departure"]
                sched_arrival = merged_stops[-1]["scheduled_arrival"]
            else:
                first_delay = timedelta(seconds=first_arrival.delay_seconds)
                last_delay = timedelta(seconds=last_arrival.delay_seconds)
                sched_departure = first_arrival.arrival_time - first_delay
                sched_arrival = last_arrival.arrival_time - last_delay

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
                stops_count=effective_stop_count,
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
                        journey_date=journey.journey_date,
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
                seen_codes: set[str] = set()
                seq = 1
                for arr in arrivals:
                    if arr.station_code in seen_codes:
                        continue
                    seen_codes.add(arr.station_code)
                    delay = timedelta(seconds=arr.delay_seconds)
                    stop = JourneyStop(
                        journey_id=journey.id,
                        journey_date=journey.journey_date,
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
                        track=None,
                        has_departed_station=False,
                        arrival_source="api_observed",
                    )
                    session.add(stop)
                    created_stops.append(stop)
                    seq += 1

            await session.flush()
            now = now_et()
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now, created_stops)
            check_journey_completed(journey, created_stops)
            logger.debug(f"Discovered SEPTA Metro train {train_id}")
            return "discovered", journey

        # Update existing journey
        journey.actual_departure = first_arrival.arrival_time
        journey.actual_arrival = last_arrival.arrival_time
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

        now = now_et()
        journey_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
        update_stop_departure_status(journey_stops, now)
        update_journey_metadata(journey, now, journey_stops)
        check_journey_completed(journey, journey_stops)
        logger.debug(f"Updated SEPTA Metro train {train_id}")
        return "updated", journey

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """JIT refresh for a single journey (called by DepartureService)."""
        if journey.data_source != DATA_SOURCE:
            return

        arrivals = await self.client.get_all_arrivals()
        journey_station_codes = {
            s.station_code for s in journey.stops if s.station_code
        }
        matching_trips = group_candidate_trips_by_overlap(
            arrivals, journey_station_codes
        )
        best_trip = select_matching_trip(
            matching_trips,
            journey,
            journey_station_codes,
            _generate_train_id,
            DATA_SOURCE,
        )
        if not best_trip:
            logger.debug(f"No matching SEPTA Metro trip for journey {journey.train_id}")
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

        journey.actual_departure = min(
            best_trip, key=lambda a: a.arrival_time
        ).arrival_time
        journey.actual_arrival = max(
            best_trip, key=lambda a: a.arrival_time
        ).arrival_time

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
        logger.debug(f"JIT updated SEPTA Metro journey {journey.train_id}")

    async def close(self) -> None:
        if self._owns_client:
            await self.client.close()
