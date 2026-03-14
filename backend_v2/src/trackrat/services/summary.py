"""
Operations summary service - Template-based natural language generation for train operations summaries.

Generates brief, human-readable summaries of recent train operations at three scopes:
- Network: Overall system status across all lines
- Route: Performance between specific origin and destination
- Train: Historical performance of a specific train
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.stations import expand_station_codes
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion_types import FREQUENCY_FIRST_SOURCES
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Time window for summaries (2 hours to capture long-haul Amtrak trains)
SUMMARY_TIME_WINDOW_MINUTES = 120

# Delay thresholds for categorization (in minutes)
ON_TIME_THRESHOLD_MINUTES = 5
SLIGHT_DELAY_THRESHOLD_MINUTES = 15

# Data freshness threshold for delay calculation (in seconds)
# When journey data is older than this, we don't trust the absence of
# actual_departure to mean the train is delayed - it may have departed
# on time but we just don't have the update yet.
DATA_FRESHNESS_THRESHOLD_SECONDS = 60

# Delay category names
DELAY_CATEGORY_ON_TIME = "on_time"
DELAY_CATEGORY_SLIGHT_DELAY = "slight_delay"
DELAY_CATEGORY_DELAYED = "delayed"
DELAY_CATEGORY_CANCELLED = "cancelled"

# Carrier data source to display name mapping
CARRIER_DISPLAY_NAMES: dict[str, str] = {
    "NJT": "NJ Transit",
    "AMTRAK": "Amtrak",
    "PATH": "PATH",
    "PATCO": "PATCO",
    "LIRR": "LIRR",
    "MNR": "Metro-North",
    "SUBWAY": "NYC Subway",
}


@dataclass
class LineStats:
    """Statistics for a single line."""

    line_name: str
    line_code: str
    train_count: int
    on_time_count: int
    cancellation_count: int
    total_delay_minutes: float
    data_source: str

    @property
    def on_time_percentage(self) -> float:
        non_cancelled = self.train_count - self.cancellation_count
        if non_cancelled <= 0:
            return 0.0
        return (self.on_time_count / non_cancelled) * 100

    @property
    def average_delay_minutes(self) -> float:
        non_cancelled = self.train_count - self.cancellation_count
        if non_cancelled <= 0:
            return 0.0
        return self.total_delay_minutes / non_cancelled


@dataclass
class SummaryMetrics:
    """Raw metrics for summary generation."""

    # Departure stats
    on_time_percentage: float | None = None
    average_delay_minutes: float | None = None
    # Arrival stats (None if no arrival data available)
    arrival_on_time_percentage: float | None = None
    arrival_average_delay_minutes: float | None = None
    # Counts
    cancellation_count: int | None = None
    train_count: int | None = None
    trains_by_category: dict[str, list[TrainDelaySummary]] | None = None


@dataclass
class OnTimeStats:
    """Statistics for on-time departure performance.

    Used consistently across train, route, and network summaries.
    Calculates stats based on departure delay from origin station.
    """

    on_time_percentage: float
    average_delay_minutes: float
    total_count: int  # Non-cancelled trains with departure data
    cancellation_count: int
    carrier_name: str | None = None  # Optional, used for route summary
    trains_by_category: dict[str, list[TrainDelaySummary]] | None = None

    @property
    def has_data(self) -> bool:
        return self.total_count > 0 or self.cancellation_count > 0

    @property
    def non_cancelled_count(self) -> int:
        return self.total_count

    @property
    def train_count_with_cancellations(self) -> int:
        return self.total_count + self.cancellation_count


@dataclass
class TrainDelaySummary:
    """Summary of a single train's delay for visualization."""

    train_id: str
    delay_minutes: float
    category: str  # on_time, slight_delay, delayed, cancelled
    scheduled_departure: datetime


@dataclass
class OperationsSummary:
    """Complete operations summary with headline and body."""

    headline: str
    body: str
    scope: Literal["network", "route", "train"]
    time_window_minutes: int
    data_freshness_seconds: int
    generated_at: datetime
    metrics: SummaryMetrics | None = None


class SummaryService:
    """Service for generating operations summaries."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[OperationsSummary, datetime]] = {}
        self._cache_ttl = 300  # 5 minutes cache

    async def get_network_summary(
        self,
        db: AsyncSession,
        data_source: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a network-wide operations summary.

        Args:
            db: Database session
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"network_{data_source or 'all'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_network_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        cutoff_time = now_et() - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query journeys in the time window
        conditions = [
            TrainJourney.last_updated_at >= cutoff_time,
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        stmt = (
            select(TrainJourney)
            .where(and_(*conditions))
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        logger.info(
            "network_summary_query",
            journey_count=len(journeys),
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_source=data_source,
        )

        # Calculate per-line statistics
        line_stats = self._calculate_line_stats(journeys)

        # Generate summary
        summary = self._generate_network_summary(line_stats)

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    async def get_route_summary(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a route-specific operations summary.

        Args:
            db: Database session
            from_station: Origin station code
            to_station: Destination station code
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"route_{from_station}_{to_station}_{data_source or 'all'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_route_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        current_time = now_et()
        cutoff_time = current_time - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query trains that departed from the origin station within the time window
        # Must be: >= cutoff_time AND <= now (already departed, not future scheduled)
        # Use actual_departure if available, otherwise scheduled_departure
        conditions = [
            or_(
                # Has actual departure within window
                and_(
                    JourneyStop.actual_departure >= cutoff_time,
                    JourneyStop.actual_departure <= current_time,
                ),
                # No actual departure yet, but scheduled within window and in the past
                and_(
                    JourneyStop.actual_departure.is_(None),
                    JourneyStop.scheduled_departure >= cutoff_time,
                    JourneyStop.scheduled_departure <= current_time,
                ),
            ),
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        # Prioritize journeys with actual departure data over scheduled-only
        # This ensures when deduplicating by train_id, we keep the most accurate record
        today = current_time.date()
        from_codes = expand_station_codes(from_station)
        to_codes_set = set(expand_station_codes(to_station))
        from_codes_set = set(from_codes)
        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_(from_codes),
                ),
            )
            .where(and_(*conditions))
            .options(selectinload(TrainJourney.stops))
            .order_by(
                # Prioritize today's journeys over stale records
                case((TrainJourney.journey_date == today, 0), else_=1),
                # Then prioritize journeys with actual departure data
                case((JourneyStop.actual_departure.isnot(None), 0), else_=1),
                # Finally by scheduled time
                JourneyStop.scheduled_departure,
            )
        )

        result = await db.execute(stmt)
        # Use .unique() to deduplicate journeys that may appear multiple times
        # when the JOIN produces multiple matching rows (e.g., duplicate stop records)
        all_journeys = list(result.scalars().unique().all())

        # Filter to journeys that actually travel to the destination
        # AND deduplicate by train_id (keep first occurrence, which is most relevant
        # due to the ORDER BY prioritization above)
        route_journeys = []
        seen_train_ids: set[str] = set()
        for journey in all_journeys:
            # Skip duplicate train_ids
            if journey.train_id in seen_train_ids:
                continue

            from_stop = None
            to_stop = None
            for stop in journey.stops:
                if stop.station_code in from_codes_set:
                    from_stop = stop
                elif stop.station_code in to_codes_set:
                    to_stop = stop

            if (
                from_stop
                and to_stop
                and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
            ):
                route_journeys.append(journey)
                if journey.train_id:
                    seen_train_ids.add(journey.train_id)

        logger.info(
            "route_summary_query",
            journey_count=len(route_journeys),
            from_station=from_station,
            to_station=to_station,
        )

        # Generate summary
        summary = self._generate_route_summary(route_journeys, from_station, to_station)

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    async def _get_similar_trains_journeys(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
    ) -> list[TrainJourney]:
        """
        Get journeys from similar trains (same route + carrier) that departed
        from the origin station within the configured time window.
        """
        current_time = now_et()
        today = current_time.date()
        cutoff_time = current_time - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query trains that departed from the origin station within the time window
        # Must be: >= cutoff_time AND <= now (already departed, not future scheduled)
        # Use actual_departure if available, otherwise scheduled_departure
        sim_from_codes = expand_station_codes(from_station)
        sim_from_codes_set = set(sim_from_codes)
        sim_to_codes_set = set(expand_station_codes(to_station))
        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_(sim_from_codes),
                ),
            )
            .where(
                and_(
                    TrainJourney.data_source == data_source,
                    or_(
                        # Has actual departure within window
                        and_(
                            JourneyStop.actual_departure >= cutoff_time,
                            JourneyStop.actual_departure <= current_time,
                        ),
                        # No actual departure yet, but scheduled within window and in the past
                        and_(
                            JourneyStop.actual_departure.is_(None),
                            JourneyStop.scheduled_departure >= cutoff_time,
                            JourneyStop.scheduled_departure <= current_time,
                        ),
                    ),
                )
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(
                # Prioritize today's journeys over stale records
                case((TrainJourney.journey_date == today, 0), else_=1),
                # Then prioritize journeys with actual departure data
                case((JourneyStop.actual_departure.isnot(None), 0), else_=1),
                # Finally by scheduled time
                JourneyStop.scheduled_departure,
            )
        )

        result = await db.execute(stmt)
        # Use .unique() to deduplicate journeys that may appear multiple times
        # when the JOIN produces multiple matching rows (e.g., duplicate stop records)
        all_journeys = list(result.scalars().unique().all())

        # Filter to journeys that actually travel to the destination
        # AND deduplicate by train_id (keep first occurrence, which is most relevant
        # due to the ORDER BY prioritization above)
        route_journeys = []
        seen_train_ids: set[str] = set()
        for journey in all_journeys:
            # Skip duplicate train_ids
            if journey.train_id in seen_train_ids:
                continue

            from_stop = None
            to_stop = None
            for stop in journey.stops:
                if stop.station_code in sim_from_codes_set:
                    from_stop = stop
                elif stop.station_code in sim_to_codes_set:
                    to_stop = stop

            if (
                from_stop
                and to_stop
                and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
            ):
                route_journeys.append(journey)
                if journey.train_id:
                    seen_train_ids.add(journey.train_id)

        return route_journeys

    async def get_train_summary(
        self,
        db: AsyncSession,
        train_id: str,
        from_station: str | None = None,
        to_station: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a train-specific operations summary combining:
        1. Similar trains' performance (same route + carrier) from the configured time window
        2. This specific train's historical performance

        Args:
            db: Database session
            train_id: Train number (e.g., "3847")
            from_station: Optional origin station code for route context
            to_station: Optional destination station code for route context

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"train_{train_id}_{from_station or 'any'}_{to_station or 'any'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_train_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        # For train summaries, look back 30 days for historical context
        cutoff_date = now_et().date() - timedelta(days=30)

        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date >= cutoff_date,
                )
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(TrainJourney.journey_date.desc())
        )

        result = await db.execute(stmt)
        train_journeys = list(result.scalars().all())

        logger.info(
            "train_summary_query",
            train_id=train_id,
            journey_count=len(train_journeys),
            days=30,
        )

        # Determine data_source: first check historical journeys, then query today's journey
        data_source: str | None = None
        if train_journeys:
            data_source = train_journeys[0].data_source or "NJT"
        elif from_station and to_station:
            # No historical data - look up today's journey to get data_source
            today = now_et().date()
            today_stmt = select(TrainJourney.data_source).where(
                and_(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date == today,
                )
            )
            today_result = await db.execute(today_stmt)
            today_data_source = today_result.scalar()
            if today_data_source:
                data_source = today_data_source
                logger.info(
                    "train_summary_data_source_from_today",
                    train_id=train_id,
                    data_source=data_source,
                )

        # Get similar trains if we have route context and data_source
        similar_journeys: list[TrainJourney] = []

        if from_station and to_station and data_source:
            similar_journeys = await self._get_similar_trains_journeys(
                db, from_station, to_station, data_source
            )
            logger.info(
                "similar_trains_query",
                train_id=train_id,
                similar_count=len(similar_journeys),
                data_source=data_source,
            )

        # Generate summary
        summary = self._generate_train_summary(
            train_journeys,
            similar_journeys,
            train_id,
            from_station,
            to_station,
            data_source,
        )

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    def _calculate_line_stats(
        self, journeys: list[TrainJourney]
    ) -> dict[str, LineStats]:
        """Calculate statistics grouped by line."""
        stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "line_name": "",
                "line_code": "",
                "train_count": 0,
                "on_time_count": 0,
                "cancellation_count": 0,
                "total_delay_minutes": 0.0,
                "data_source": "",
            }
        )

        for journey in journeys:
            line_key = journey.line_name or journey.line_code or "Unknown"
            line_data = stats[line_key]

            line_data["line_name"] = journey.line_name or line_key
            line_data["line_code"] = journey.line_code or ""
            line_data["data_source"] = journey.data_source
            line_data["train_count"] += 1

            if journey.is_cancelled:
                line_data["cancellation_count"] += 1
            else:
                # Calculate delay from last stop
                if journey.stops:
                    last_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)
                    if last_stop.actual_arrival and last_stop.scheduled_arrival:
                        # Exclude scheduled_fallback arrivals — they always show
                        # 0 delay (actual == scheduled) and inflate on-time stats
                        if last_stop.arrival_source == "scheduled_fallback":
                            pass
                        else:
                            delay = (
                                last_stop.actual_arrival - last_stop.scheduled_arrival
                            ).total_seconds() / 60
                            line_data["total_delay_minutes"] += max(0, delay)
                            if delay <= ON_TIME_THRESHOLD_MINUTES:
                                line_data["on_time_count"] += 1
                    else:
                        # No arrival data (in-progress), assume on time
                        line_data["on_time_count"] += 1

        return {
            key: LineStats(
                line_name=data["line_name"],
                line_code=data["line_code"],
                train_count=data["train_count"],
                on_time_count=data["on_time_count"],
                cancellation_count=data["cancellation_count"],
                total_delay_minutes=data["total_delay_minutes"],
                data_source=data["data_source"],
            )
            for key, data in stats.items()
        }

    def _generate_network_summary(
        self, line_stats: dict[str, LineStats]
    ) -> OperationsSummary:
        """Generate network-wide summary from line statistics."""
        if not line_stats:
            logger.info(
                "network_summary_empty",
                reason="no_line_stats",
                message="Returning empty body - no train data in time window",
            )
            return OperationsSummary(
                headline="",
                body="",
                scope="network",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Aggregate totals (note: line_stats uses arrival-based on-time)
        total_trains = sum(ls.train_count for ls in line_stats.values())
        total_on_time = sum(ls.on_time_count for ls in line_stats.values())
        total_cancellations = sum(ls.cancellation_count for ls in line_stats.values())
        total_delay = sum(ls.total_delay_minutes for ls in line_stats.values())

        non_cancelled = total_trains - total_cancellations
        on_time_pct = (total_on_time / non_cancelled * 100) if non_cancelled > 0 else 0
        avg_delay = total_delay / non_cancelled if non_cancelled > 0 else 0

        # Generate headline and body
        headline, body = self._format_network_headline_body(
            on_time_pct, avg_delay, total_cancellations
        )

        logger.info(
            "network_summary_generated",
            total_trains=total_trains,
            on_time_pct=round(on_time_pct, 1),
            avg_delay=round(avg_delay, 1),
            cancellations=total_cancellations,
            line_count=len(line_stats),
            headline=headline,
            body_length=len(body),
        )

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="network",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=now_et(),
            metrics=SummaryMetrics(
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
                arrival_on_time_percentage=on_time_pct,  # Network uses arrival stats
                arrival_average_delay_minutes=avg_delay,
                cancellation_count=total_cancellations,
                train_count=total_trains,
            ),
        )

    def _format_network_headline_body(
        self, on_time_pct: float, avg_delay: float, cancellations: int
    ) -> tuple[str, str]:
        """
        Format headline and body for network summary.

        Rules:
        - Cancellations lead the headline when present
        - Network scope shows arrival-based stats (trains completing journeys)
        """
        # Determine headline - cancellations take priority
        if cancellations > 0:
            cancel_word = "cancellation" if cancellations == 1 else "cancellations"
            headline = f"{cancellations} {cancel_word}"
        elif on_time_pct >= 95 and avg_delay < 5:
            headline = "Trains running smoothly"
        elif on_time_pct >= 85:
            headline = "Mostly on time"
        elif on_time_pct >= 75:
            headline = "Some network delays"
        else:
            headline = "Significant delays"

        # Build body
        body_parts = []

        # Cancellation notice first
        if cancellations > 0:
            train_word = "train" if cancellations == 1 else "trains"
            body_parts.append(f"{cancellations} {train_word} cancelled.")

        # Main status message
        if avg_delay < 1:
            body_parts.append(f"{on_time_pct:.0f}% of trains arriving on time.")
        else:
            body_parts.append(
                f"{on_time_pct:.0f}% arriving on time with average delays of {avg_delay:.0f} minutes."
            )

        return headline, " ".join(body_parts)

    def _categorize_delay(self, delay_minutes: float) -> str:
        """Categorize a delay into on_time, slight_delay, or delayed."""
        if delay_minutes <= ON_TIME_THRESHOLD_MINUTES:
            return DELAY_CATEGORY_ON_TIME
        elif delay_minutes <= SLIGHT_DELAY_THRESHOLD_MINUTES:
            return DELAY_CATEGORY_SLIGHT_DELAY
        else:
            return DELAY_CATEGORY_DELAYED

    def _merge_trains_by_category(
        self, *stats_list: OnTimeStats | None
    ) -> dict[str, list[TrainDelaySummary]]:
        """Merge trains_by_category from multiple OnTimeStats into one dict."""
        merged: dict[str, list[TrainDelaySummary]] = {
            DELAY_CATEGORY_ON_TIME: [],
            DELAY_CATEGORY_SLIGHT_DELAY: [],
            DELAY_CATEGORY_DELAYED: [],
            DELAY_CATEGORY_CANCELLED: [],
        }
        for stats in stats_list:
            if stats and stats.trains_by_category:
                for category, trains in stats.trains_by_category.items():
                    merged[category].extend(trains)
        # Sort each category by scheduled departure
        for category in merged:
            merged[category].sort(key=lambda t: t.scheduled_departure)
        return merged

    def _calculate_departure_stats(
        self,
        journeys: list[TrainJourney],
        from_station: str,
        carrier_name: str | None = None,
        current_time: datetime | None = None,
    ) -> OnTimeStats:
        """
        Calculate on-time departure statistics for a list of journeys.

        Uses departure delay from the origin station, which is more reliable
        than arrival delay for recent trains that haven't completed their journey.

        Args:
            journeys: List of journeys to analyze
            from_station: Origin station code to measure departure delay
            carrier_name: Optional carrier name for route summaries
            current_time: Current time for calculating delay of not-yet-departed trains

        Returns:
            OnTimeStats with percentage, delay, counts, and trains by category
        """
        if current_time is None:
            current_time = now_et()

        from_codes_set = set(expand_station_codes(from_station))

        on_time_count = 0
        cancellation_count = 0
        total_delay = 0.0
        counted_trains = 0

        # Collect trains by category for visualization
        trains_by_category: dict[str, list[TrainDelaySummary]] = {
            DELAY_CATEGORY_ON_TIME: [],
            DELAY_CATEGORY_SLIGHT_DELAY: [],
            DELAY_CATEGORY_DELAYED: [],
            DELAY_CATEGORY_CANCELLED: [],
        }

        for journey in journeys:
            # Skip journeys without train_id (required for TrainDelaySummary)
            if not journey.train_id:
                continue

            if journey.is_cancelled:
                cancellation_count += 1
                # Find scheduled departure for cancelled trains
                from_stop = next(
                    (s for s in journey.stops if s.station_code in from_codes_set),
                    None,
                )
                if from_stop and from_stop.scheduled_departure:
                    trains_by_category[DELAY_CATEGORY_CANCELLED].append(
                        TrainDelaySummary(
                            train_id=journey.train_id,
                            delay_minutes=0.0,
                            category=DELAY_CATEGORY_CANCELLED,
                            scheduled_departure=from_stop.scheduled_departure,
                        )
                    )
                continue

            # Find the origin stop for departure delay calculation
            from_stop = next(
                (s for s in journey.stops if s.station_code in from_codes_set),
                None,
            )

            if from_stop and from_stop.scheduled_departure:
                counted_trains += 1
                if from_stop.actual_departure:
                    delay = (
                        from_stop.actual_departure - from_stop.scheduled_departure
                    ).total_seconds() / 60
                    delay = max(0, delay)
                    total_delay += delay
                    if delay <= ON_TIME_THRESHOLD_MINUTES:
                        on_time_count += 1
                    category = self._categorize_delay(delay)
                else:
                    # No actual departure yet - calculate how late based on current time
                    time_since_scheduled = (
                        current_time - from_stop.scheduled_departure
                    ).total_seconds() / 60
                    if time_since_scheduled <= ON_TIME_THRESHOLD_MINUTES:
                        # Just scheduled, might still depart on time
                        on_time_count += 1
                        delay = 0.0
                        category = DELAY_CATEGORY_ON_TIME
                    else:
                        # Past scheduled time with no actual departure data.
                        # Check if journey data is fresh enough to trust the
                        # absence of actual_departure as an indication of delay.
                        data_age_seconds = (
                            (current_time - journey.last_updated_at).total_seconds()
                            if journey.last_updated_at
                            else float("inf")
                        )

                        if data_age_seconds <= DATA_FRESHNESS_THRESHOLD_SECONDS:
                            # Fresh data - trust that no departure means delayed
                            delay = time_since_scheduled
                            total_delay += time_since_scheduled
                            category = self._categorize_delay(delay)
                        else:
                            # Stale data - don't assume delay; train may have
                            # departed on time but we don't have the update.
                            on_time_count += 1
                            delay = 0.0
                            category = DELAY_CATEGORY_ON_TIME

                trains_by_category[category].append(
                    TrainDelaySummary(
                        train_id=journey.train_id,
                        delay_minutes=delay,
                        category=category,
                        scheduled_departure=from_stop.scheduled_departure,
                    )
                )

        if counted_trains == 0 and cancellation_count == 0:
            return OnTimeStats(
                on_time_percentage=0.0,
                average_delay_minutes=0.0,
                total_count=0,
                cancellation_count=0,
                carrier_name=carrier_name,
                trains_by_category=trains_by_category,
            )

        # On-time percentage based on non-cancelled trains
        on_time_pct = (
            (on_time_count / counted_trains * 100) if counted_trains > 0 else 0.0
        )
        avg_delay = (total_delay / counted_trains) if counted_trains > 0 else 0.0

        return OnTimeStats(
            on_time_percentage=on_time_pct,
            average_delay_minutes=avg_delay,
            total_count=counted_trains,
            cancellation_count=cancellation_count,
            carrier_name=carrier_name,
            trains_by_category=trains_by_category,
        )

    def _calculate_arrival_stats(
        self,
        journeys: list[TrainJourney],
        to_station: str,
    ) -> OnTimeStats | None:
        """
        Calculate on-time arrival statistics for a list of journeys.

        Uses arrival delay at the destination station. Only includes journeys
        that have actual arrival data (completed journeys).

        Args:
            journeys: List of journeys to analyze
            to_station: Destination station code to measure arrival delay

        Returns:
            OnTimeStats with arrival data, or None if no arrival data available
        """
        on_time_count = 0
        total_delay = 0.0
        counted_trains = 0
        to_codes_set = set(expand_station_codes(to_station))

        for journey in journeys:
            # Skip cancelled journeys
            if journey.is_cancelled:
                continue

            # Find the destination stop for arrival delay calculation
            to_stop = next(
                (s for s in journey.stops if s.station_code in to_codes_set), None
            )

            if to_stop and to_stop.scheduled_arrival and to_stop.actual_arrival:
                counted_trains += 1
                delay = (
                    to_stop.actual_arrival - to_stop.scheduled_arrival
                ).total_seconds() / 60
                delay = max(0, delay)
                total_delay += delay
                if delay <= ON_TIME_THRESHOLD_MINUTES:
                    on_time_count += 1

        # Return None if no arrival data available
        if counted_trains == 0:
            return None

        on_time_pct = on_time_count / counted_trains * 100
        avg_delay = total_delay / counted_trains

        return OnTimeStats(
            on_time_percentage=on_time_pct,
            average_delay_minutes=avg_delay,
            total_count=counted_trains,
            cancellation_count=0,  # Already filtered out
            trains_by_category=None,
        )

    def _format_carrier_description(self, stats: OnTimeStats) -> str:
        """Format a single carrier's statistics as a sentence fragment."""
        total = stats.train_count_with_cancellations
        train_word = "train" if total == 1 else "trains"

        # Base: "there were 9 NJ Transit trains on your route with 100% departing on time"
        desc = (
            f"there {'was' if total == 1 else 'were'} {total} {stats.carrier_name} {train_word} on your route "
            f"with {stats.on_time_percentage:.0f}% departing on time"
        )

        # Add delay and/or cancellation info in parentheses if applicable
        extras = []
        if stats.total_count > 0 and stats.average_delay_minutes >= 1:
            extras.append(f"{stats.average_delay_minutes:.0f} min avg delay")
        if stats.cancellation_count > 0:
            extras.append(f"{stats.cancellation_count} cancelled")

        if extras:
            desc += f" ({', '.join(extras)})"

        return desc

    def _generate_route_summary(
        self,
        journeys: list[TrainJourney],
        from_station: str,
        to_station: str,
    ) -> OperationsSummary:
        """Generate route-specific summary with departure and arrival stats."""
        current_time = now_et()

        if not journeys:
            return OperationsSummary(
                headline="",
                body="No trains travelled your route in the past 2 hours.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=None,
            )

        # Calculate stats for each carrier
        carrier_dep_stats: dict[str, OnTimeStats] = {}
        carrier_arr_stats: dict[str, OnTimeStats] = {}

        for data_source, display_name in CARRIER_DISPLAY_NAMES.items():
            carrier_journeys = [j for j in journeys if j.data_source == data_source]
            if carrier_journeys:
                carrier_dep_stats[data_source] = self._calculate_departure_stats(
                    carrier_journeys, from_station, display_name, current_time
                )
                arr_stats = self._calculate_arrival_stats(carrier_journeys, to_station)
                if arr_stats is not None:
                    carrier_arr_stats[data_source] = arr_stats

        # Aggregate departure metrics from all carriers
        total_trains = sum(
            s.train_count_with_cancellations for s in carrier_dep_stats.values()
        )
        total_non_cancelled = sum(s.total_count for s in carrier_dep_stats.values())
        total_cancellations = sum(
            s.cancellation_count for s in carrier_dep_stats.values()
        )

        # Merge trains by category from all carriers
        merged_trains = self._merge_trains_by_category(*carrier_dep_stats.values())

        # Handle all-cancelled scenario
        if total_non_cancelled == 0 and total_cancellations > 0:
            cancel_word = (
                "cancellation" if total_cancellations == 1 else "cancellations"
            )
            return OperationsSummary(
                headline=f"{total_cancellations} {cancel_word}",
                body="All scheduled trains were cancelled in the past 2 hours.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=SummaryMetrics(
                    on_time_percentage=0.0,
                    average_delay_minutes=0.0,
                    arrival_on_time_percentage=None,
                    arrival_average_delay_minutes=None,
                    cancellation_count=total_cancellations,
                    train_count=total_trains,
                    trains_by_category=merged_trains,
                ),
            )

        # Calculate weighted departure averages
        if total_non_cancelled > 0:
            dep_on_time_pct = (
                sum(
                    s.on_time_percentage * s.total_count
                    for s in carrier_dep_stats.values()
                )
                / total_non_cancelled
            )
            dep_avg_delay = (
                sum(
                    s.average_delay_minutes * s.total_count
                    for s in carrier_dep_stats.values()
                )
                / total_non_cancelled
            )
        else:
            dep_on_time_pct = 0.0
            dep_avg_delay = 0.0

        # Calculate weighted arrival averages (may be None if no arrival data)
        arr_on_time_pct: float | None = None
        arr_avg_delay: float | None = None
        arr_total = sum(s.total_count for s in carrier_arr_stats.values())
        if arr_total > 0:
            arr_on_time_pct = (
                sum(
                    s.on_time_percentage * s.total_count
                    for s in carrier_arr_stats.values()
                )
                / arr_total
            )
            arr_avg_delay = (
                sum(
                    s.average_delay_minutes * s.total_count
                    for s in carrier_arr_stats.values()
                )
                / arr_total
            )

        # Detect if this is a frequency-first route (subway, PATH, PATCO)
        is_frequency_route = all(
            ds in FREQUENCY_FIRST_SOURCES for ds in carrier_dep_stats
        )

        # Generate headline and body
        if is_frequency_route:
            headline, body = self._format_frequency_route_headline_body(
                total_non_cancelled,
                total_cancellations,
            )
        else:
            headline, body = self._format_route_headline_body(
                dep_on_time_pct,
                dep_avg_delay,
                arr_on_time_pct,
                arr_avg_delay,
                total_cancellations,
            )

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="route",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=current_time,
            metrics=SummaryMetrics(
                on_time_percentage=dep_on_time_pct,
                average_delay_minutes=dep_avg_delay,
                arrival_on_time_percentage=arr_on_time_pct,
                arrival_average_delay_minutes=arr_avg_delay,
                cancellation_count=total_cancellations,
                train_count=total_trains,
                trains_by_category=merged_trains,
            ),
        )

    def _format_route_headline_body(
        self,
        dep_on_time_pct: float,
        dep_avg_delay: float,
        arr_on_time_pct: float | None,
        arr_avg_delay: float | None,
        cancellations: int,
    ) -> tuple[str, str]:
        """
        Format headline and body for route summary.

        Body format: "{status}, {arrival}."
        - Status based on cancellations or departure on-time percentage
        - Arrival based on average arrival delay
        """
        # Headline - cancellations lead when present
        if cancellations > 0:
            cancel_word = "cancellation" if cancellations == 1 else "cancellations"
            headline = f"{cancellations} {cancel_word}"
        else:
            headline = f"Past two hours: {dep_on_time_pct:.0f}% on time"

        # Status clause
        if cancellations > 0:
            status = "Trains cancelled"
            connector = ", the rest "
        elif dep_on_time_pct >= 90:
            status = "Trains departing on time"
            connector = ", "
        elif dep_on_time_pct >= 65:
            status = "Most trains departing on time"
            connector = ", "
        else:
            status = "Trains delayed"
            connector = ", "

        # Arrival clause
        if arr_avg_delay is not None and arr_avg_delay >= 1:
            mins = int(round(arr_avg_delay))
            minute_word = "minute" if mins == 1 else "minutes"
            arrival = f"arriving {mins} {minute_word} late"
        elif arr_on_time_pct is not None:
            arrival = "arriving roughly on schedule"
        else:
            arrival = None

        # Combine
        if arrival:
            body = f"{status}{connector}{arrival}."
        else:
            body = f"{status}."

        return headline, body

    def _format_frequency_route_headline_body(
        self,
        train_count: int,
        cancellations: int,
    ) -> tuple[str, str]:
        """
        Format headline and body for frequency-first route summary (subway, PATH, PATCO).

        Emphasizes train count and headway rather than on-time percentage,
        since riders of frequent-service systems care about "how often"
        not "is the 3:42 on time."
        """
        if cancellations > 0:
            cancel_word = "cancellation" if cancellations == 1 else "cancellations"
            headline = f"{cancellations} {cancel_word}"
        elif train_count > 0:
            headway = SUMMARY_TIME_WINDOW_MINUTES / train_count
            headline = f"Past two hours: every ~{headway:.0f} min"
        else:
            headline = "Past two hours: 0 trains"

        # Body
        body_parts = []
        if cancellations > 0:
            remaining = train_count
            cancel_word = "train was" if cancellations == 1 else "trains were"
            body_parts.append(f"{cancellations} {cancel_word} cancelled.")
            if remaining > 0:
                headway = SUMMARY_TIME_WINDOW_MINUTES / remaining
                body_parts.append(
                    f"{remaining} others departed, averaging every {headway:.0f} minutes."
                )
        elif train_count > 0:
            headway = SUMMARY_TIME_WINDOW_MINUTES / train_count
            body_parts.append(
                f"Trains running every {headway:.0f} minutes."
            )
        else:
            body_parts.append(
                f"No trains departed in the past {SUMMARY_TIME_WINDOW_MINUTES // 60} hours."
            )

        return headline, " ".join(body_parts)

    def _calculate_historical_departure_stats(
        self,
        journeys: list[TrainJourney],
    ) -> OnTimeStats:
        """
        Calculate on-time departure stats for historical journeys.

        Uses each journey's actual origin station (first stop) for departure delay,
        since historical journeys may have different origins.

        Args:
            journeys: List of historical journeys to analyze

        Returns:
            OnTimeStats with percentage, delay, and counts
        """
        on_time_count = 0
        cancellation_count = 0
        total_delay = 0.0
        counted_trains = 0

        for journey in journeys:
            if journey.is_cancelled:
                cancellation_count += 1
                continue

            if not journey.stops:
                continue

            # Use the first stop (origin) for departure delay
            first_stop = min(journey.stops, key=lambda s: s.stop_sequence or 0)

            if first_stop and first_stop.scheduled_departure:
                counted_trains += 1
                if first_stop.actual_departure:
                    delay = (
                        first_stop.actual_departure - first_stop.scheduled_departure
                    ).total_seconds() / 60
                    delay = max(0, delay)
                    total_delay += delay
                    if delay <= ON_TIME_THRESHOLD_MINUTES:
                        on_time_count += 1
                else:
                    # Has scheduled but no actual - assume on time
                    on_time_count += 1

        if counted_trains == 0 and cancellation_count == 0:
            return OnTimeStats(
                on_time_percentage=0.0,
                average_delay_minutes=0.0,
                total_count=0,
                cancellation_count=0,
                trains_by_category=None,
            )

        on_time_pct = (
            (on_time_count / counted_trains * 100) if counted_trains > 0 else 0.0
        )
        avg_delay = (total_delay / counted_trains) if counted_trains > 0 else 0.0

        return OnTimeStats(
            on_time_percentage=on_time_pct,
            average_delay_minutes=avg_delay,
            total_count=counted_trains,
            cancellation_count=cancellation_count,
            trains_by_category=None,
        )

    def _generate_train_summary(
        self,
        train_journeys: list[TrainJourney],
        similar_journeys: list[TrainJourney],
        train_id: str,
        from_station: str | None,
        to_station: str | None,
        data_source: str | None,
    ) -> OperationsSummary:
        """
        Generate train-specific summary combining similar trains and historical data.

        Args:
            train_journeys: Historical journeys for this specific train
            similar_journeys: Recent journeys from similar trains (same route + carrier)
            train_id: Train number
            from_station: Origin station code
            to_station: Destination station code
            data_source: Carrier (NJT or AMTRAK)
        """
        current_time = now_et()

        # Calculate departure stats for similar trains (configured time window)
        if from_station and similar_journeys:
            similar_dep_stats = self._calculate_departure_stats(
                similar_journeys, from_station, current_time=current_time
            )
        else:
            similar_dep_stats = OnTimeStats(
                on_time_percentage=0.0,
                average_delay_minutes=0.0,
                total_count=0,
                cancellation_count=0,
            )

        # Calculate arrival stats for similar trains
        similar_arr_stats: OnTimeStats | None = None
        if to_station and similar_journeys:
            similar_arr_stats = self._calculate_arrival_stats(
                similar_journeys, to_station
            )

        # Calculate stats for this specific train (historical)
        train_stats = self._calculate_historical_departure_stats(train_journeys)

        carrier_name = CARRIER_DISPLAY_NAMES.get(data_source or "")

        # Total cancellations from similar trains
        total_cancellations = similar_dep_stats.cancellation_count

        # Get destination for display (used for PATH/PATCO friendly names)
        destination = train_journeys[0].destination if train_journeys else None

        # Generate headline and body
        is_frequency_system = data_source in FREQUENCY_FIRST_SOURCES
        if is_frequency_system:
            headline, body = self._format_frequency_train_headline_body(
                similar_dep_stats,
                train_stats,
                total_cancellations,
                destination=destination,
            )
        else:
            headline, body = self._format_train_headline_body(
                similar_dep_stats,
                similar_arr_stats,
                train_stats,
                train_id,
                carrier_name,
                total_cancellations,
                destination=destination,
                data_source=data_source,
            )

        if not headline:
            # No data at all
            return OperationsSummary(
                headline="",
                body="",
                scope="train",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=None,
            )

        # Build metrics
        arr_on_time_pct = (
            similar_arr_stats.on_time_percentage if similar_arr_stats else None
        )
        arr_avg_delay = (
            similar_arr_stats.average_delay_minutes if similar_arr_stats else None
        )

        if train_stats.has_data:
            metrics = SummaryMetrics(
                on_time_percentage=train_stats.on_time_percentage,
                average_delay_minutes=train_stats.average_delay_minutes,
                arrival_on_time_percentage=arr_on_time_pct,
                arrival_average_delay_minutes=arr_avg_delay,
                cancellation_count=train_stats.cancellation_count,
                train_count=train_stats.total_count,
            )
        elif similar_dep_stats.has_data:
            metrics = SummaryMetrics(
                on_time_percentage=similar_dep_stats.on_time_percentage,
                average_delay_minutes=similar_dep_stats.average_delay_minutes,
                arrival_on_time_percentage=arr_on_time_pct,
                arrival_average_delay_minutes=arr_avg_delay,
                cancellation_count=similar_dep_stats.cancellation_count,
                train_count=similar_dep_stats.total_count,
            )
        else:
            metrics = None

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="train",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=current_time,
            metrics=metrics,
        )

    def _format_train_headline_body(
        self,
        dep_stats: OnTimeStats,
        arr_stats: OnTimeStats | None,
        train_stats: OnTimeStats,
        train_id: str,
        carrier_name: str | None,
        cancellations: int,
        destination: str | None = None,
        data_source: str | None = None,
    ) -> tuple[str, str]:
        """
        Format headline and body for train summary.

        Rules:
        - Cancellations lead the headline when present
        - Show departure % and arrival delay for similar trains
        - Show historical stats for this specific train
        """
        body_parts = []

        # Determine headline - always show on-time percentage
        if cancellations > 0:
            cancel_word = "cancellation" if cancellations == 1 else "cancellations"
            headline = f"{cancellations} {cancel_word}"
        elif dep_stats.has_data:
            headline = f"Past two hours: {dep_stats.on_time_percentage:.0f}% on time"
        elif train_stats.has_data:
            headline = f"Past two hours: {train_stats.on_time_percentage:.0f}% on time"
        else:
            return "", ""  # No data

        # Cancellation notice first
        if cancellations > 0:
            train_word = "train" if cancellations == 1 else "trains"
            body_parts.append(f"{cancellations} similar {train_word} cancelled.")

        # Similar trains stats (past 90 min)
        if dep_stats.has_data and carrier_name:
            arr_avg = arr_stats.average_delay_minutes if arr_stats else None
            if arr_avg is not None and arr_avg >= 1:
                body_parts.append(
                    f"{dep_stats.on_time_percentage:.0f}% of similar {carrier_name} trains "
                    f"departing on time, averaging {arr_avg:.0f} minutes late on arrival."
                )
            elif arr_stats is not None:
                body_parts.append(
                    f"{dep_stats.on_time_percentage:.0f}% of similar {carrier_name} trains "
                    f"departing on time, arriving within schedule."
                )
            else:
                body_parts.append(
                    f"{dep_stats.on_time_percentage:.0f}% of similar {carrier_name} trains "
                    f"departing on time."
                )

        # Historical stats for this train
        # For PATH/PATCO/LIRR/MNR, use destination instead of synthetic train_id
        if train_stats.has_data:
            if (
                data_source in ("PATH", "PATCO", "LIRR", "MNR", "SUBWAY")
                and destination
            ):
                train_display = f"This {destination} train"
            else:
                train_display = f"Train {train_id}"
            hist_text = f"{train_display} historically departs on time {train_stats.on_time_percentage:.0f}% of the time."
            if train_stats.cancellation_count > 0:
                hist_text += (
                    f" Cancelled {train_stats.cancellation_count} "
                    f"time{'s' if train_stats.cancellation_count != 1 else ''} in past 30 days."
                )
            body_parts.append(hist_text)

        return headline, " ".join(body_parts)

    def _format_frequency_train_headline_body(
        self,
        dep_stats: OnTimeStats,
        train_stats: OnTimeStats,
        cancellations: int,
        destination: str | None = None,
    ) -> tuple[str, str]:
        """
        Format headline and body for frequency-first train summary (subway, PATH, PATCO).

        Emphasizes recent train count / headway for similar trains,
        and historical frequency for this specific train.
        """
        similar_count = dep_stats.total_count
        similar_total = similar_count + dep_stats.cancellation_count

        # Headline
        if cancellations > 0:
            cancel_word = "cancellation" if cancellations == 1 else "cancellations"
            headline = f"{cancellations} {cancel_word}"
        elif similar_total > 0:
            headway = SUMMARY_TIME_WINDOW_MINUTES / similar_total
            headline = f"Past two hours: every ~{headway:.0f} min"
        elif train_stats.has_data:
            headline = f"Historically ~{train_stats.total_count} trains per month"
        else:
            return "", ""

        # Body
        body_parts = []

        if cancellations > 0:
            cancel_word = "train" if cancellations == 1 else "trains"
            body_parts.append(f"{cancellations} similar {cancel_word} cancelled.")

        if similar_count > 0:
            headway = SUMMARY_TIME_WINDOW_MINUTES / similar_count
            body_parts.append(
                f"{similar_count} similar trains departed in the past "
                f"{SUMMARY_TIME_WINDOW_MINUTES // 60} hours, "
                f"averaging every {headway:.0f} minutes."
            )

        if train_stats.has_data:
            train_display = f"This {destination} train" if destination else "This train"
            hist_text = f"{train_display} historically departs on time {train_stats.on_time_percentage:.0f}% of the time."
            if train_stats.cancellation_count > 0:
                hist_text += (
                    f" Cancelled {train_stats.cancellation_count} "
                    f"time{'s' if train_stats.cancellation_count != 1 else ''} in past 30 days."
                )
            body_parts.append(hist_text)

        return headline, " ".join(body_parts)


summary_service = SummaryService()
