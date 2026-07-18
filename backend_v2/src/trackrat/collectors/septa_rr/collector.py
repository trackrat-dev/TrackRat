"""SEPTA Regional Rail unified collector.

SEPTA's Regional Rail GTFS-RT feed is delay-based (see ``client.py``), so this
collector always joins the GTFS static schedule to reconstruct absolute stop
times before handing off to the shared ``mta_common`` machinery. A trip with no
matching static schedule is skipped — there is nothing to reconstruct from.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.mta_common import (
    JOURNEY_UPDATE_LOAD_OPTIONS,
    build_complete_stops,
    check_journey_completed,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.collectors.septa_rr.client import (
    SeptaRailArrival,
    SeptaRailClient,
    SeptaRailTripUpdate,
)
from trackrat.config.stations import get_septa_rr_route_info, get_station_name
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_et

logger = logging.getLogger(__name__)

DATA_SOURCE = "SEPTA_RR"
_DEFAULT_LINE_COLOR = "#4F758B"  # SEPTA Regional Rail blue

# Outer bound on the feed fetch, generous vs the client's own HTTP timeout but
# well within the scheduler task budget so a hung upstream can't starve it.
_FEED_FETCH_TIMEOUT_SECONDS = 60.0


def _generate_train_id(trip_id: str) -> str:
    """Derive a stable train id from a SEPTA trip_id.

    SEPTA RR trip_ids are ``<short_name>_<YYYYMMDD>_<SID...>`` (e.g.
    ``CHW8312_20260718_SID189411``); the first segment is the GTFS
    ``trip_short_name`` (``CHW8312``), unique per service day.
    """
    return trip_id.split("_", 1)[0] or trip_id


def _parse_journey_date(trip_id: str) -> date:
    """Extract the service date embedded in a SEPTA trip_id (``_YYYYMMDD_``)."""
    parts = trip_id.split("_")
    if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
        try:
            return datetime.strptime(parts[1], "%Y%m%d").date()
        except ValueError:
            pass
    return now_et().date()


def resolve_arrivals(
    trip: SeptaRailTripUpdate, static_stops: list[dict[str, Any]]
) -> list[SeptaRailArrival]:
    """Turn delay updates + the static schedule into absolute-time arrivals.

    GTFS-RT delay semantics: a stop_time_update's delay applies to its stop and
    every later stop until the next update. Stops before the first update have
    already been passed and are left for ``build_complete_stops`` to backfill.
    """
    updates = sorted(trip.stop_updates, key=lambda u: u.stop_sequence)
    if not updates:
        return []
    first_rt_seq = updates[0].stop_sequence

    arrivals: list[SeptaRailArrival] = []
    for stop in static_stops:
        seq = stop["stop_sequence"]
        if seq is None or seq < first_rt_seq:
            continue  # already passed — backfilled from static

        # Applicable delay = the latest update at or before this sequence.
        applicable = updates[0]
        for upd in updates:
            if upd.stop_sequence <= seq:
                applicable = upd
            else:
                break
        arr_delay = applicable.arrival_delay
        if arr_delay is None:
            arr_delay = applicable.departure_delay or 0
        dep_delay = applicable.departure_delay
        if dep_delay is None:
            dep_delay = arr_delay

        sched_arr = stop["arrival_time"] or stop["departure_time"]
        sched_dep = stop["departure_time"] or stop["arrival_time"]
        if sched_arr is None:
            continue

        arrivals.append(
            SeptaRailArrival(
                station_code=stop["station_code"],
                trip_id=trip.trip_id,
                route_id=trip.route_id,
                direction_id=trip.direction_id,
                arrival_time=sched_arr + timedelta(seconds=arr_delay),
                departure_time=(
                    sched_dep + timedelta(seconds=dep_delay) if sched_dep else None
                ),
                delay_seconds=arr_delay,
                track=None,
            )
        )
    return arrivals


class SeptaRailCollector:
    """Discovers SEPTA Regional Rail trains and updates their journeys."""

    def __init__(self, client: SeptaRailClient | None = None) -> None:
        self.client = client or SeptaRailClient()
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
        stats = {"discovered": 0, "updated": 0, "expired": 0, "errors": 0, "trips": 0}

        try:
            collection_start = now_et()
            try:
                trip_updates = await asyncio.wait_for(
                    self.client.get_trip_updates(),
                    timeout=_FEED_FETCH_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "septa_rr_feed_fetch_timed_out | timeout_s=%.1f",
                    _FEED_FETCH_TIMEOUT_SECONDS,
                )
                return stats

            stats["trips"] = len(trip_updates)
            if not trip_updates:
                logger.warning("No SEPTA RR trips found in GTFS-RT feed")
                return stats

            batch_size = 50
            trips_in_batch = 0
            analyzed_journeys: list[TrainJourney] = []
            for trip in trip_updates:
                try:
                    async with session.begin_nested():
                        result, journey = await self._process_trip(session, trip)
                        if result == "discovered":
                            stats["discovered"] += 1
                        elif result == "updated":
                            stats["updated"] += 1
                        if journey is not None and journey.id is not None:
                            analyzed_journeys.append(journey)
                except Exception as e:
                    logger.error(f"Error processing SEPTA RR trip {trip.trip_id}: {e}")
                    stats["errors"] += 1

                trips_in_batch += 1
                if trips_in_batch >= batch_size:
                    await session.commit()
                    trips_in_batch = 0

            if stats["errors"] > 0 and stats["discovered"] + stats["updated"] == 0:
                raise RuntimeError(
                    f"SEPTA RR collection: all {stats['errors']} trips failed"
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
                f"SEPTA RR collection complete: {stats['discovered']} discovered, "
                f"{stats['updated']} updated, {stats['expired']} expired, "
                f"{stats['errors']} errors"
            )
        except Exception as e:
            logger.error(f"SEPTA RR collection failed: {e}")
            await session.rollback()
            stats["errors"] += 1

        return stats

    async def _process_trip(
        self, session: AsyncSession, trip: SeptaRailTripUpdate
    ) -> tuple[str | None, TrainJourney | None]:
        train_id = _generate_train_id(trip.trip_id)
        journey_date = _parse_journey_date(trip.trip_id)

        route_info = get_septa_rr_route_info(trip.route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = f"SEPTA-{trip.route_id}"
            line_name = f"SEPTA {trip.route_id}"
            line_color = _DEFAULT_LINE_COLOR

        # Regional Rail's feed carries no absolute times — the static schedule is
        # mandatory. Without it there is nothing to reconstruct, so skip.
        static_stops = await self._gtfs_service.get_static_stop_times(
            session, DATA_SOURCE, trip.trip_id, journey_date
        )
        if not static_stops:
            logger.debug(
                "SEPTA RR static schedule unavailable for trip %s; skipping",
                trip.trip_id,
            )
            return None, None

        arrivals = resolve_arrivals(trip, static_stops)
        if not arrivals:
            return None, None

        merged_stops, origin_code, terminal_code = build_complete_stops(
            arrivals, static_stops
        )
        if len(merged_stops) < 2:
            logger.debug(
                "Skipping SEPTA RR trip %s: only %d usable stop(s)",
                trip.trip_id,
                len(merged_stops),
            )
            return None, None

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
        first_arrival = min(arrivals, key=lambda a: a.arrival_time)

        if journey is None:
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
                scheduled_departure=merged_stops[0]["scheduled_departure"],
                scheduled_arrival=merged_stops[-1]["scheduled_arrival"],
                actual_departure=first_arrival.arrival_time,
                has_complete_journey=True,
                stops_count=len(merged_stops),
                is_cancelled=False,
                is_completed=False,
                api_error_count=0,
                is_expired=False,
                discovery_station_code=first_arrival.station_code,
            )
            session.add(journey)
            await session.flush()

            created_stops: list[JourneyStop] = []
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

            await session.flush()
            now = now_et()
            update_stop_departure_status(created_stops, now)
            update_journey_metadata(journey, now, created_stops)
            check_journey_completed(journey, created_stops)
            logger.debug(f"Discovered SEPTA RR train {train_id}")
            return "discovered", journey

        # Update existing journey with fresh predictions.
        journey.actual_departure = first_arrival.arrival_time
        journey.actual_arrival = max(
            arrivals, key=lambda a: a.arrival_time
        ).arrival_time
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
        logger.debug(f"Updated SEPTA RR train {train_id}")
        return "updated", journey

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """JIT refresh for a single journey (called by DepartureService)."""
        if journey.data_source != DATA_SOURCE or journey.journey_date is None:
            return

        trip_updates = await self.client.get_trip_updates()
        trip = next(
            (
                t
                for t in trip_updates
                if _generate_train_id(t.trip_id) == journey.train_id
            ),
            None,
        )
        if trip is None:
            logger.debug(f"No matching SEPTA RR trip for journey {journey.train_id}")
            return

        static_stops = await self._gtfs_service.get_static_stop_times(
            session, DATA_SOURCE, trip.trip_id, journey.journey_date
        )
        if not static_stops:
            return
        arrivals = resolve_arrivals(trip, static_stops)
        if not arrivals:
            return

        stop_result = await session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        journey_stops = list(stop_result.scalars().all())
        stops_by_code = {s.station_code: s for s in journey_stops}
        for arr in arrivals:
            stop = stops_by_code.get(arr.station_code)
            if stop:
                stop.actual_arrival = arr.arrival_time
                stop.updated_arrival = arr.arrival_time
                stop.arrival_source = "api_observed"
                if arr.departure_time:
                    stop.actual_departure = arr.departure_time
                    stop.updated_departure = arr.departure_time

        journey.actual_departure = min(
            arrivals, key=lambda a: a.arrival_time
        ).arrival_time
        journey.actual_arrival = max(
            arrivals, key=lambda a: a.arrival_time
        ).arrival_time

        now = now_et()
        update_stop_departure_status(journey_stops, now)
        update_journey_metadata(journey, now, journey_stops)
        check_journey_completed(journey, journey_stops)
        logger.debug(f"JIT updated SEPTA RR journey {journey.train_id}")

    async def close(self) -> None:
        if self._owns_client:
            await self.client.close()
