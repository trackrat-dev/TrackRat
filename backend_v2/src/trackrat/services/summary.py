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

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Fixed time window for summaries (90 minutes as per requirements)
SUMMARY_TIME_WINDOW_MINUTES = 90


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

    on_time_percentage: float | None = None
    average_delay_minutes: float | None = None
    cancellation_count: int | None = None
    train_count: int | None = None


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

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code == from_station,
                ),
            )
            .where(and_(*conditions))
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys that actually travel to the destination
        route_journeys = []
        for journey in all_journeys:
            from_stop = None
            to_stop = None
            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_stop = stop
                elif stop.station_code == to_station:
                    to_stop = stop

            if (
                from_stop
                and to_stop
                and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
            ):
                route_journeys.append(journey)

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
        from the origin station in the past 90 minutes.
        """
        current_time = now_et()
        cutoff_time = current_time - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query trains that departed from the origin station within the time window
        # Must be: >= cutoff_time AND <= now (already departed, not future scheduled)
        # Use actual_departure if available, otherwise scheduled_departure
        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code == from_station,
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
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys that actually travel to the destination
        route_journeys = []
        for journey in all_journeys:
            from_stop = None
            to_stop = None
            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_stop = stop
                elif stop.station_code == to_station:
                    to_stop = stop

            if (
                from_stop
                and to_stop
                and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
            ):
                route_journeys.append(journey)

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
        1. Similar trains' performance (same route + carrier) from past 90 minutes
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
                        delay = (
                            last_stop.actual_arrival - last_stop.scheduled_arrival
                        ).total_seconds() / 60
                        line_data["total_delay_minutes"] += max(0, delay)
                        if delay <= 5:
                            line_data["on_time_count"] += 1
                    else:
                        # No arrival data, assume on time
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
            # No data - return empty so iOS can hide the section
            return OperationsSummary(
                headline="",
                body="",
                scope="network",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Aggregate totals
        total_trains = sum(ls.train_count for ls in line_stats.values())
        total_on_time = sum(ls.on_time_count for ls in line_stats.values())
        total_cancellations = sum(ls.cancellation_count for ls in line_stats.values())
        total_delay = sum(ls.total_delay_minutes for ls in line_stats.values())

        non_cancelled = total_trains - total_cancellations
        on_time_pct = (total_on_time / non_cancelled * 100) if non_cancelled > 0 else 0
        avg_delay = total_delay / non_cancelled if non_cancelled > 0 else 0

        # Generate headline
        headline = self._get_network_headline(
            on_time_pct, avg_delay, total_cancellations
        )

        # Generate body
        body_parts = []

        # Lead sentence
        if on_time_pct >= 85:
            body_parts.append(
                f"Most trains running on time with average delays of {avg_delay:.0f} minutes."
            )
        elif on_time_pct >= 70:
            body_parts.append(
                f"Some delays across the network. {on_time_pct:.0f}% of trains on schedule, "
                f"averaging {avg_delay:.0f} minute delays."
            )
        else:
            body_parts.append(
                f"Widespread delays today. Only {on_time_pct:.0f}% of trains running on time, "
                f"with delays averaging {avg_delay:.0f} minutes."
            )

        # Per-line breakdown for lines with issues
        problem_lines = [
            ls
            for ls in line_stats.values()
            if ls.cancellation_count > 0 or ls.average_delay_minutes > 10
        ]

        if problem_lines:
            for ls in sorted(
                problem_lines, key=lambda x: x.cancellation_count, reverse=True
            )[:2]:
                if ls.cancellation_count > 0:
                    body_parts.append(
                        f"{ls.line_name}: {ls.cancellation_count} cancellation(s), "
                        f"averaging {ls.average_delay_minutes:.0f} min delays."
                    )
                elif ls.average_delay_minutes > 10:
                    body_parts.append(
                        f"{ls.line_name}: averaging {ls.average_delay_minutes:.0f} min delays."
                    )

        body = " ".join(body_parts)

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
                cancellation_count=total_cancellations,
                train_count=total_trains,
            ),
        )

    def _get_network_headline(
        self, on_time_pct: float, avg_delay: float, cancellations: int
    ) -> str:
        """Generate a concise headline based on network status."""
        if on_time_pct >= 95 and avg_delay < 3:
            return "Trains running smoothly"
        elif on_time_pct >= 85 and avg_delay < 6:
            return "Trains mostly on time"
        elif on_time_pct >= 70 and avg_delay < 10:
            return "Some delays across network"
        elif on_time_pct >= 50:
            return "Widespread delays today"
        else:
            return "Major disruptions"

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
            OnTimeStats with percentage, delay, and counts
        """
        if current_time is None:
            current_time = now_et()

        on_time_count = 0
        cancellation_count = 0
        total_delay = 0.0
        counted_trains = 0

        for journey in journeys:
            if journey.is_cancelled:
                cancellation_count += 1
                continue

            # Find the origin stop for departure delay calculation
            from_stop = next(
                (s for s in journey.stops if s.station_code == from_station), None
            )

            if from_stop and from_stop.scheduled_departure:
                counted_trains += 1
                if from_stop.actual_departure:
                    delay = (
                        from_stop.actual_departure - from_stop.scheduled_departure
                    ).total_seconds() / 60
                    delay = max(0, delay)
                    total_delay += delay
                    if delay <= 5:
                        on_time_count += 1
                else:
                    # No actual departure yet - calculate how late based on current time
                    time_since_scheduled = (
                        current_time - from_stop.scheduled_departure
                    ).total_seconds() / 60
                    if time_since_scheduled <= 5:
                        # Just scheduled, might still depart on time
                        on_time_count += 1
                    else:
                        # Significantly past scheduled time - count as delayed
                        total_delay += time_since_scheduled

        if counted_trains == 0 and cancellation_count == 0:
            return OnTimeStats(
                on_time_percentage=0.0,
                average_delay_minutes=0.0,
                total_count=0,
                cancellation_count=0,
                carrier_name=carrier_name,
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
        )

    def _format_carrier_description(self, stats: OnTimeStats) -> str:
        """Format a single carrier's statistics as a sentence fragment."""
        total = stats.train_count_with_cancellations
        train_word = "train" if total == 1 else "trains"

        # Base: "there were 9 NJ Transit trains on this route with 100% departing on time"
        desc = (
            f"there {'was' if total == 1 else 'were'} {total} {stats.carrier_name} {train_word} on this route "
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
        """Generate route-specific summary with carrier breakdown."""
        current_time = now_et()

        if not journeys:
            # No trains scheduled in the window - inform the user
            return OperationsSummary(
                headline="",
                body="No trains scheduled on this route in the past 90 minutes.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=None,
            )

        # Group journeys by carrier
        njt_journeys = [j for j in journeys if j.data_source == "NJT"]
        amtrak_journeys = [j for j in journeys if j.data_source == "AMTRAK"]

        # Calculate stats for each carrier using departure delay
        njt_stats = (
            self._calculate_departure_stats(
                njt_journeys, from_station, "NJ Transit", current_time
            )
            if njt_journeys
            else None
        )
        amtrak_stats = (
            self._calculate_departure_stats(
                amtrak_journeys, from_station, "Amtrak", current_time
            )
            if amtrak_journeys
            else None
        )

        # Calculate aggregate metrics for the response
        total_trains = (
            njt_stats.train_count_with_cancellations if njt_stats else 0
        ) + (amtrak_stats.train_count_with_cancellations if amtrak_stats else 0)
        total_non_cancelled = (njt_stats.total_count if njt_stats else 0) + (
            amtrak_stats.total_count if amtrak_stats else 0
        )
        total_cancellations = (njt_stats.cancellation_count if njt_stats else 0) + (
            amtrak_stats.cancellation_count if amtrak_stats else 0
        )

        # Handle all-cancelled scenario
        if total_non_cancelled == 0 and total_cancellations > 0:
            train_word = "train was" if total_cancellations == 1 else "trains were"
            return OperationsSummary(
                headline="Service disrupted",
                body=f"All {total_cancellations} scheduled {train_word} cancelled in the past 90 minutes.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=SummaryMetrics(
                    on_time_percentage=0.0,
                    average_delay_minutes=0.0,
                    cancellation_count=total_cancellations,
                    train_count=total_trains,
                ),
            )

        # Build carrier descriptions
        carrier_descriptions = []
        if njt_stats and njt_stats.has_data:
            carrier_descriptions.append(self._format_carrier_description(njt_stats))
        if amtrak_stats and amtrak_stats.has_data:
            carrier_descriptions.append(self._format_carrier_description(amtrak_stats))

        # Build body text
        if len(carrier_descriptions) == 1:
            body = f"Over the past 90 minutes, {carrier_descriptions[0]}."
        elif len(carrier_descriptions) > 1:
            # Join with period and space for multiple carriers
            body = f"Over the past 90 minutes, {carrier_descriptions[0]}.\n\nT{carrier_descriptions[1][1:]}."
        else:
            body = "No departure data available for the past 90 minutes."

        # Calculate weighted average for on-time and delay
        if total_non_cancelled > 0:
            njt_weight = njt_stats.total_count if njt_stats else 0
            amtrak_weight = amtrak_stats.total_count if amtrak_stats else 0
            on_time_pct = (
                (njt_stats.on_time_percentage * njt_weight if njt_stats else 0)
                + (
                    amtrak_stats.on_time_percentage * amtrak_weight
                    if amtrak_stats
                    else 0
                )
            ) / total_non_cancelled
            avg_delay = (
                (njt_stats.average_delay_minutes * njt_weight if njt_stats else 0)
                + (
                    amtrak_stats.average_delay_minutes * amtrak_weight
                    if amtrak_stats
                    else 0
                )
            ) / total_non_cancelled
        else:
            on_time_pct = 0.0
            avg_delay = 0.0

        # Generate headline matching train scope format
        headline = f"Recent departures: {on_time_pct:.0f}% on time"

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="route",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=current_time,
            metrics=SummaryMetrics(
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
                cancellation_count=total_cancellations,
                train_count=total_trains,
            ),
        )

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
                    if delay <= 5:
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

        # Calculate stats for similar trains (past 90 minutes) using departure from user's origin
        if from_station and similar_journeys:
            similar_stats = self._calculate_departure_stats(
                similar_journeys, from_station, current_time=current_time
            )
        else:
            similar_stats = OnTimeStats(
                on_time_percentage=0.0,
                average_delay_minutes=0.0,
                total_count=0,
                cancellation_count=0,
            )

        # Calculate stats for this specific train (historical) using each journey's origin
        train_stats = self._calculate_historical_departure_stats(train_journeys)

        carrier_name = (
            "NJ Transit" if data_source == "NJT" else "Amtrak" if data_source else None
        )

        # Generate headline
        if similar_stats.has_data:
            headline = (
                f"Recent departures: {similar_stats.on_time_percentage:.0f}% on time"
            )
        else:
            headline = "View On-Time Stats"

        # Generate body
        body_parts = []

        if similar_stats.has_data and carrier_name:
            similar_text = (
                f"There {'was' if similar_stats.total_count == 1 else 'were'} {similar_stats.total_count} similar {carrier_name} "
                f"train{'s' if similar_stats.total_count != 1 else ''} in the past 90 minutes and "
                f"{similar_stats.on_time_percentage:.0f}% departed on-time"
            )
            if similar_stats.average_delay_minutes >= 1:
                similar_text += (
                    f" ({similar_stats.average_delay_minutes:.0f} min avg delay)"
                )
            similar_text += "."

            # Add cancellation info for similar trains
            if similar_stats.cancellation_count > 0:
                similar_text += (
                    f" {similar_stats.cancellation_count} "
                    f"{'was' if similar_stats.cancellation_count == 1 else 'were'} cancelled."
                )

            similar_text += "\n"
            body_parts.append(similar_text)

        if train_stats.has_data:
            train_text = (
                f"\nTrain {train_id} historically departs on time "
                f"{train_stats.on_time_percentage:.0f}% of the time"
            )
            if train_stats.average_delay_minutes >= 1:
                train_text += (
                    f" ({train_stats.average_delay_minutes:.0f} min avg delay)"
                )
            train_text += "."

            # Add cancellation info for this train's history
            if train_stats.cancellation_count > 0:
                train_text += (
                    f" It has been cancelled {train_stats.cancellation_count} "
                    f"time{'s' if train_stats.cancellation_count != 1 else ''} "
                    f"in the past 30 days."
                )

            body_parts.append(train_text)

        if not body_parts:
            # No data at all - return summary with empty headline so iOS can hide the section
            return OperationsSummary(
                headline="",
                body="",
                scope="train",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=current_time,
                metrics=None,
            )

        body = " ".join(body_parts)

        # Use train stats for metrics if available, otherwise similar trains
        if train_stats.has_data:
            metrics = SummaryMetrics(
                on_time_percentage=train_stats.on_time_percentage,
                average_delay_minutes=train_stats.average_delay_minutes,
                cancellation_count=train_stats.cancellation_count,
                train_count=train_stats.total_count,
            )
        elif similar_stats.has_data:
            metrics = SummaryMetrics(
                on_time_percentage=similar_stats.on_time_percentage,
                average_delay_minutes=similar_stats.average_delay_minutes,
                cancellation_count=similar_stats.cancellation_count,
                train_count=similar_stats.total_count,
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
