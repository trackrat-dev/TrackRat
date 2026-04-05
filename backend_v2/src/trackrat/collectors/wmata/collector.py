"""
Unified WMATA (Washington DC Metro) collector for TrackRat V2.

Combines discovery and journey tracking into a single task that:
1. Fetches predictions for all stations (single API call)
2. Optionally fetches train positions for ID correlation
3. Discovers new trains and creates journey records
4. Updates existing journeys with real-time arrival data

Runs every 3 minutes. Modeled after the PATH collector pattern.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.wmata.client import (
    WMATAClient,
    WMATAPrediction,
    WMATATrainPosition,
)
from trackrat.config.stations import get_station_name
from trackrat.config.stations.wmata import (
    DEFAULT_MINUTES_PER_SEGMENT,
    WMATA_STATION_NAMES,
    get_wmata_route_and_stops,
    get_wmata_route_info,
    infer_wmata_origin,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.locks import with_train_lock
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Deduplication: time window for matching existing journeys (minutes)
DEDUP_TIME_WINDOW_MINUTES = 5

# After this many consecutive missed update cycles, mark journey as expired
MISSED_CYCLES_BEFORE_EXPIRY = 3

# Grace period after scheduled arrival before marking stop as departed (minutes)
DEPARTURE_GRACE_MINUTES = 2

# Weight factor: closer stops have more influence on origin time estimation
# Weight = 1 / (cumulative_minutes + 1) to avoid division by zero for origin


class WMATACollector:
    """Unified WMATA collector - discovers and updates in one pass."""

    def __init__(self, client: WMATAClient | None = None) -> None:
        """Initialize the WMATA collector.

        Args:
            client: Optional WMATA client (creates one if not provided)
        """
        self.client = client  # Will be set from settings if None
        self._owns_client = client is None

    def _ensure_client(self) -> bool:
        """Ensure client is initialized from settings if needed.

        Returns:
            True if client is available, False if no API key configured.
        """
        if self.client is not None:
            return True
        from trackrat.settings import get_settings

        settings = get_settings()
        if not settings.wmata_api_key:
            return False
        self.client = WMATAClient(api_key=settings.wmata_api_key)
        self._owns_client = True
        return True

    async def run(self) -> dict[str, Any]:
        """Main entry point with session management.

        Returns:
            Collection results summary
        """
        if not self._ensure_client():
            logger.warning(
                "wmata_collection_skipped", reason="no API key configured"
            )
            return {
                "data_source": "WMATA",
                "error": "no API key",
                "arrivals_fetched": 0,
            }

        try:
            async with get_session() as session:
                return await self.collect(session)
        finally:
            if self._owns_client and self.client is not None:
                await self.client.close()
                self.client = None

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Run unified WMATA collection.

        Two API calls serve both discovery and updates:
        1. GetPrediction/All - arrivals at all stations
        2. TrainPositions - supplement with train IDs (best-effort)

        Args:
            session: Database session

        Returns:
            Collection results summary
        """
        if self.client is None:
            raise RuntimeError("WMATA client not initialized")
        logger.info("wmata_collection_started")

        # === API CALLS ===
        try:
            predictions = await self.client.get_all_predictions()
        except Exception as e:
            logger.error("wmata_predictions_api_failed", error=str(e))
            return {
                "data_source": "WMATA",
                "error": str(e),
                "arrivals_fetched": 0,
                "new_journeys": 0,
                "updated": 0,
                "completed": 0,
            }

        # Train positions are supplementary - don't fail if unavailable
        positions: list[WMATATrainPosition] = []
        try:
            positions = await self.client.get_train_positions()
        except Exception as e:
            logger.warning("wmata_positions_api_failed", error=str(e))

        # === PHASE 1: DISCOVERY ===
        discovery_stats = await self._discover_trains(session, predictions, positions)

        # === PHASE 2: UPDATES ===
        update_stats = await self._update_journeys(session, predictions)

        await session.commit()

        logger.info(
            "wmata_collection_completed",
            predictions_fetched=len(predictions),
            positions_fetched=len(positions),
            new_journeys=discovery_stats["new_journeys"],
            journeys_updated=update_stats["updated"],
            journeys_completed=update_stats["completed"],
        )

        return {
            "data_source": "WMATA",
            "arrivals_fetched": len(predictions),
            **discovery_stats,
            **update_stats,
        }

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """JIT update for a single WMATA journey.

        Called by the JIT service when a user requests fresh data.

        Args:
            session: Database session
            journey: Journey to update
        """
        if not self._ensure_client():
            logger.warning(
                "wmata_jit_skipped",
                train_id=journey.train_id,
                reason="no API key configured",
            )
            return

        await with_train_lock(
            journey.train_id or "",
            str(journey.journey_date),
            self._collect_journey_details_locked,
            session,
            journey,
        )

    async def _collect_journey_details_locked(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Inner JIT update logic, called under train lock."""
        if self.client is None:
            raise RuntimeError("WMATA client not initialized")

        try:
            predictions = await self.client.get_all_predictions()
        except Exception as e:
            logger.warning(
                "wmata_jit_api_failed",
                train_id=journey.train_id,
                error=str(e),
            )
            journey.api_error_count = (journey.api_error_count or 0) + 1
            if journey.api_error_count >= 3:
                journey.is_expired = True
            return

        # Load stops
        stops_result = await session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = list(stops_result.scalars().all())
        if not stops:
            return

        # Filter predictions relevant to this journey
        relevant = [
            p
            for p in predictions
            if p.line == journey.line_code
            and p.destination_code == journey.terminal_station_code
        ]

        self._update_stops_from_predictions(journey, stops, relevant)

    # =========================================================================
    # PHASE 1: DISCOVERY
    # =========================================================================

    async def _discover_trains(
        self,
        session: AsyncSession,
        predictions: list[WMATAPrediction],
        positions: list[WMATATrainPosition],
    ) -> dict[str, Any]:
        """Discovery phase - create journeys for new trains.

        Groups predictions by (line, destination, group) to identify unique
        trains, then creates journey records for trains not yet tracked.
        """
        now = now_et()
        today = now.date()
        new_journeys = 0
        skipped_existing = 0

        # Group predictions to identify unique trains.
        # Each unique (line, destination_code, location_code, group) that has
        # a numeric minutes value represents a train approaching that station.
        # We want to find trains we haven't seen yet.
        #
        # Strategy: for each (line, destination_code, group), take the prediction
        # with the LARGEST minutes value at any station — that's the train
        # farthest from its destination, giving us the best origin estimate.
        train_groups: dict[tuple[str, str, str], list[WMATAPrediction]] = defaultdict(
            list
        )

        for pred in predictions:
            if pred.minutes is None:
                continue
            dest_code = pred.destination_code
            if not dest_code:
                continue
            key = (pred.line, dest_code, pred.group)
            train_groups[key].append(pred)

        for (line, dest_code, _group), preds in train_groups.items():
            if not preds:
                continue

            # Sort by minutes descending — the prediction with most minutes
            # is the train farthest from destination (closest to origin)
            preds.sort(key=lambda p: p.minutes or 0, reverse=True)
            farthest = preds[0]

            # Infer origin
            origin_code = infer_wmata_origin(line, dest_code)
            if not origin_code:
                continue

            # Calculate estimated origin departure time
            route_result = get_wmata_route_and_stops(origin_code, dest_code, line)
            if not route_result:
                continue
            route_line, route_stops = route_result

            # Find farthest prediction's station in the route
            if farthest.location_code not in route_stops:
                continue
            farthest_idx = route_stops.index(farthest.location_code)

            # Back-calculate origin departure:
            # Time from origin to farthest station = farthest_idx * segment_time
            # Arrival at farthest station = now + farthest.minutes
            # Origin departure = arrival at farthest - travel time to farthest
            travel_to_farthest = farthest_idx * DEFAULT_MINUTES_PER_SEGMENT
            farthest_arrival = now + timedelta(minutes=farthest.minutes or 0)
            origin_departure = farthest_arrival - timedelta(minutes=travel_to_farthest)

            # Generate synthetic train ID
            train_id = _generate_wmata_train_id(line, dest_code, origin_departure)

            # === DEDUPLICATION ===
            # Check 1: exact train_id + date + source
            existing = await session.execute(
                select(TrainJourney.id)
                .where(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date == today,
                    TrainJourney.data_source == "WMATA",
                )
                .with_for_update(skip_locked=True)
            )
            if existing.scalar_one_or_none() is not None:
                skipped_existing += 1
                continue

            # Check 2: fuzzy match — same line, destination, within time window
            time_window_start = origin_departure - timedelta(
                minutes=DEDUP_TIME_WINDOW_MINUTES
            )
            time_window_end = origin_departure + timedelta(
                minutes=DEDUP_TIME_WINDOW_MINUTES
            )
            fuzzy_match = await session.execute(
                select(TrainJourney.id)
                .where(
                    TrainJourney.data_source == "WMATA",
                    TrainJourney.journey_date == today,
                    TrainJourney.line_code == line,
                    TrainJourney.terminal_station_code == dest_code,
                    TrainJourney.scheduled_departure >= time_window_start,
                    TrainJourney.scheduled_departure <= time_window_end,
                    TrainJourney.is_completed == False,  # noqa: E712
                    TrainJourney.is_expired == False,  # noqa: E712
                )
                .with_for_update(skip_locked=True)
            )
            if fuzzy_match.scalars().first() is not None:
                skipped_existing += 1
                continue

            # === CREATE JOURNEY ===
            route_info = get_wmata_route_info(line)
            if not route_info:
                continue
            line_code, line_name, line_color = route_info

            total_travel = len(route_stops) * DEFAULT_MINUTES_PER_SEGMENT
            scheduled_arrival = origin_departure + timedelta(minutes=total_travel)

            journey = TrainJourney(
                train_id=train_id,
                journey_date=today,
                line_code=line_code,
                line_name=line_name,
                line_color=line_color,
                destination=WMATA_STATION_NAMES.get(dest_code, dest_code),
                origin_station_code=origin_code,
                terminal_station_code=dest_code,
                data_source="WMATA",
                observation_type="OBSERVED",
                scheduled_departure=origin_departure,
                scheduled_arrival=scheduled_arrival,
                has_complete_journey=True,
                stops_count=len(route_stops),
            )
            session.add(journey)
            await session.flush()

            # Create journey stops
            await self._create_journey_stops(
                session, journey, route_stops, origin_departure, farthest.location_code
            )

            new_journeys += 1

        return {
            "new_journeys": new_journeys,
            "skipped_existing": skipped_existing,
        }

    async def _create_journey_stops(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        route_stops: list[str],
        origin_departure: datetime,
        discovery_station: str,
    ) -> None:
        """Create JourneyStop records for all stops in a journey.

        Args:
            session: Database session
            journey: Parent journey
            route_stops: Ordered station codes
            origin_departure: Estimated departure time from origin
            discovery_station: Station where train was first observed
        """
        discovery_idx = (
            route_stops.index(discovery_station)
            if discovery_station in route_stops
            else -1
        )

        for seq, station_code in enumerate(route_stops):
            cumulative_min = seq * DEFAULT_MINUTES_PER_SEGMENT
            stop_time = origin_departure + timedelta(minutes=cumulative_min)

            is_origin = seq == 0
            is_terminal = seq == len(route_stops) - 1

            # For stops before discovery station: mark as already departed
            has_departed = discovery_idx >= 0 and seq < discovery_idx

            stop = JourneyStop(
                journey_id=journey.id,
                station_code=station_code,
                station_name=get_station_name(station_code),
                stop_sequence=seq + 1,
                scheduled_arrival=None if is_origin else stop_time,
                scheduled_departure=None if is_terminal else stop_time,
                updated_arrival=None if is_origin else stop_time,
                updated_departure=None if is_terminal else stop_time,
                actual_arrival=stop_time if has_departed else None,
                actual_departure=stop_time if has_departed else None,
                has_departed_station=has_departed,
                departure_source="inferred_from_discovery" if has_departed else None,
                arrival_source="scheduled_fallback" if has_departed else None,
            )
            session.add(stop)

    # =========================================================================
    # PHASE 2: UPDATES
    # =========================================================================

    async def _update_journeys(
        self,
        session: AsyncSession,
        predictions: list[WMATAPrediction],
    ) -> dict[str, Any]:
        """Update phase - refresh existing journeys with new prediction data.

        Args:
            session: Database session
            predictions: Current predictions from API
        """
        now = now_et()
        today = now.date()
        updated = 0
        completed = 0

        # Load all active WMATA journeys for today
        result = await session.execute(
            select(TrainJourney).where(
                TrainJourney.data_source == "WMATA",
                TrainJourney.journey_date == today,
                TrainJourney.is_completed == False,  # noqa: E712
                TrainJourney.is_expired == False,  # noqa: E712
                TrainJourney.is_cancelled == False,  # noqa: E712
            )
        )
        journeys = list(result.scalars().all())

        if not journeys:
            return {"updated": 0, "completed": 0}

        # Index predictions by (line, destination_code) for fast lookup
        pred_by_line_dest: dict[tuple[str, str | None], list[WMATAPrediction]] = (
            defaultdict(list)
        )
        for pred in predictions:
            pred_by_line_dest[(pred.line, pred.destination_code)].append(pred)

        for journey in journeys:
            # Get matching predictions
            line_code = journey.line_code or ""
            matching_preds = pred_by_line_dest.get(
                (line_code, journey.terminal_station_code), []
            )

            # Load stops
            stops_result = await session.execute(
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence)
            )
            stops = list(stops_result.scalars().all())
            if not stops:
                continue

            was_updated = self._update_stops_from_predictions(
                journey, stops, matching_preds
            )

            if was_updated:
                updated += 1

            # Check completion: terminal stop departed
            terminal_stop = stops[-1]
            if terminal_stop.has_departed_station and not journey.is_completed:
                journey.is_completed = True
                journey.actual_arrival = terminal_stop.actual_arrival or now
                completed += 1

                # Trigger analytics on completion
                try:
                    analyzer = TransitAnalyzer()
                    await analyzer.analyze_journey(session, journey)
                except Exception as e:
                    logger.warning(
                        "wmata_journey_analysis_failed",
                        train_id=journey.train_id,
                        error=str(e),
                    )

            # Expiry check: if scheduled arrival is well past and no predictions match
            if (
                not journey.is_completed
                and journey.scheduled_arrival
                and now > journey.scheduled_arrival + timedelta(minutes=10)
                and not matching_preds
            ):
                journey.api_error_count = (journey.api_error_count or 0) + 1
                if journey.api_error_count >= MISSED_CYCLES_BEFORE_EXPIRY:
                    journey.is_expired = True
                    logger.debug(
                        "wmata_journey_expired",
                        train_id=journey.train_id,
                        reason="no_matching_predictions",
                    )

            # Create/update snapshot
            await self._create_snapshot(session, journey, stops)

        return {"updated": updated, "completed": completed}

    def _update_stops_from_predictions(
        self,
        journey: TrainJourney,
        stops: list[JourneyStop],
        predictions: list[WMATAPrediction],
    ) -> bool:
        """Update journey stops using current predictions.

        For each stop, try to find a matching prediction (same station).
        If found with minutes == 0 or is_arriving/is_boarding, mark as departed.

        Returns True if any stop was updated.
        """
        now = now_et()
        any_updated = False

        # Index predictions by station
        preds_by_station: dict[str, list[WMATAPrediction]] = defaultdict(list)
        for pred in predictions:
            preds_by_station[pred.location_code].append(pred)

        last_departed_idx = -1

        for idx, stop in enumerate(stops):
            if stop.has_departed_station:
                last_departed_idx = idx
                continue

            station_preds = preds_by_station.get(stop.station_code or "", [])

            # Find best matching prediction for this stop
            best_pred = self._find_best_prediction(stop, station_preds)

            if best_pred is not None:
                if (
                    best_pred.is_arriving
                    or best_pred.is_boarding
                    or best_pred.minutes == 0
                ):
                    # Train is at or past this station
                    stop.has_departed_station = True
                    stop.actual_arrival = now
                    stop.actual_departure = now
                    stop.departure_source = "wmata_prediction"
                    stop.arrival_source = "wmata_prediction"
                    last_departed_idx = idx
                    any_updated = True
                elif best_pred.minutes is not None:
                    # Update predicted arrival time
                    predicted_arrival = now + timedelta(minutes=best_pred.minutes)
                    stop.updated_arrival = predicted_arrival
                    stop.updated_departure = predicted_arrival
                    any_updated = True
            else:
                # No matching prediction — check if we should infer departure
                # If scheduled time is well past, mark as departed
                sched = stop.scheduled_arrival or stop.scheduled_departure
                if sched and now > sched + timedelta(minutes=DEPARTURE_GRACE_MINUTES):
                    # Only if a later stop already has a prediction or is departed
                    should_infer = False
                    for later_stop in stops[idx + 1 :]:
                        later_preds = preds_by_station.get(
                            later_stop.station_code or "", []
                        )
                        if later_stop.has_departed_station or later_preds:
                            should_infer = True
                            break

                    if should_infer:
                        stop.has_departed_station = True
                        stop.actual_arrival = sched
                        stop.actual_departure = sched
                        stop.departure_source = "inferred_time"
                        stop.arrival_source = "inferred_time"
                        last_departed_idx = idx
                        any_updated = True

        # Sequential consistency: if stop N is departed, all stops < N must be
        if last_departed_idx > 0:
            for idx in range(last_departed_idx):
                stop = stops[idx]
                if not stop.has_departed_station:
                    sched = stop.scheduled_arrival or stop.scheduled_departure
                    stop.has_departed_station = True
                    stop.actual_arrival = stop.actual_arrival or sched or now
                    stop.actual_departure = stop.actual_departure or sched or now
                    stop.departure_source = (
                        stop.departure_source or "inferred_sequential"
                    )
                    stop.arrival_source = stop.arrival_source or "inferred_sequential"
                    any_updated = True

        return any_updated

    def _find_best_prediction(
        self,
        stop: JourneyStop,
        station_preds: list[WMATAPrediction],
    ) -> WMATAPrediction | None:
        """Find the best matching prediction for a journey stop.

        Matches by station code and validates the time is reasonable.
        """
        if not station_preds:
            return None

        now = now_et()

        # If there's only one prediction for this station, use it
        if len(station_preds) == 1:
            return station_preds[0]

        # Multiple predictions — pick the one closest to scheduled time
        sched = stop.scheduled_arrival or stop.scheduled_departure
        if not sched:
            return station_preds[0]

        best: WMATAPrediction | None = None
        best_diff = float("inf")

        for pred in station_preds:
            if pred.minutes is None:
                continue
            predicted_time = now + timedelta(minutes=pred.minutes)
            diff = abs((predicted_time - sched).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best = pred

        # Also consider ARR/BRD predictions
        for pred in station_preds:
            if pred.is_arriving or pred.is_boarding:
                if sched and now >= sched - timedelta(
                    minutes=DEDUP_TIME_WINDOW_MINUTES
                ):
                    return pred

        return best

    async def _create_snapshot(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops: list[JourneyStop],
    ) -> None:
        """Create or replace journey snapshot."""
        # Delete existing snapshots for this journey
        await session.execute(
            delete(JourneySnapshot).where(JourneySnapshot.journey_id == journey.id)
        )

        completed_stops = sum(1 for s in stops if s.has_departed_station)
        total_stops = len(stops)

        if journey.is_completed:
            status = "completed"
        elif completed_stops > 0:
            status = "in_transit"
        else:
            status = "scheduled"

        snapshot = JourneySnapshot(
            journey_id=journey.id,
            captured_at=now_et(),
            train_status=status,
            completed_stops=completed_stops,
            total_stops=total_stops,
            raw_stop_list_data={},
        )
        session.add(snapshot)


def _generate_wmata_train_id(
    line_code: str,
    destination_code: str,
    departure_time: datetime,
) -> str:
    """Generate a synthetic train ID for WMATA.

    Format: WMATA_{line}_{dest}_{unix_timestamp_rounded_to_minute}

    The departure time is rounded to the nearest minute to prevent the same
    physical train from getting different IDs when observed at different
    stations (which may yield slightly different back-calculated times).

    Args:
        line_code: WMATA line code (e.g., "RD")
        destination_code: Destination station code (e.g., "A15")
        departure_time: Estimated origin departure time

    Returns:
        Synthetic train ID string
    """
    # Round to nearest minute
    rounded = departure_time.replace(second=0, microsecond=0)
    if departure_time.second >= 30:
        rounded += timedelta(minutes=1)
    ts = int(rounded.timestamp())
    return f"WMATA_{line_code}_{destination_code}_{ts}"
