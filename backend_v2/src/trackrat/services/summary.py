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
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.stations import get_station_name
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ensure_timezone_aware, now_et

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
class CarrierRouteStats:
    """Statistics for a single carrier on a route."""

    carrier_name: str  # "NJ Transit" or "Amtrak"
    train_count: int
    on_time_count: int
    cancellation_count: int
    total_delay_minutes: float

    @property
    def non_cancelled_count(self) -> int:
        return self.train_count - self.cancellation_count

    @property
    def on_time_percentage(self) -> float:
        if self.non_cancelled_count <= 0:
            return 0.0
        return (self.on_time_count / self.non_cancelled_count) * 100

    @property
    def average_delay_minutes(self) -> float:
        if self.non_cancelled_count <= 0:
            return 0.0
        return self.total_delay_minutes / self.non_cancelled_count


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

        cutoff_time = now_et() - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query journeys that include both stations
        conditions = [
            TrainJourney.last_updated_at >= cutoff_time,
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_([from_station, to_station]),
                ),
            )
            .where(and_(*conditions))
            .group_by(TrainJourney.id)
            .having(func.count(func.distinct(JourneyStop.station_code)) == 2)
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys that actually travel from origin to destination
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
        Get journeys from similar trains (same route + carrier) in the past 90 minutes.
        """
        cutoff_time = now_et() - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_([from_station, to_station]),
                ),
            )
            .where(
                and_(
                    TrainJourney.last_updated_at >= cutoff_time,
                    TrainJourney.data_source == data_source,
                )
            )
            .group_by(TrainJourney.id)
            .having(func.count(func.distinct(JourneyStop.station_code)) == 2)
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys that actually travel from origin to destination
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

        # Get similar trains if we have route context
        similar_journeys: list[TrainJourney] = []
        data_source: str | None = None

        if from_station and to_station and train_journeys:
            # Determine carrier from this train's journeys
            data_source = train_journeys[0].data_source
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
        stats: dict[str, dict] = defaultdict(
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
            return OperationsSummary(
                headline="No recent train data",
                body="No train operations recorded in the past 90 minutes.",
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

    def _calculate_carrier_route_stats(
        self,
        journeys: list[TrainJourney],
        to_station: str,
    ) -> CarrierRouteStats | None:
        """Calculate route statistics for a list of journeys from the same carrier."""
        if not journeys:
            return None

        # Determine carrier name from first journey
        data_source = journeys[0].data_source
        carrier_name = "NJ Transit" if data_source == "NJT" else "Amtrak"

        on_time_count = 0
        cancellation_count = 0
        total_delay = 0.0

        for journey in journeys:
            if journey.is_cancelled:
                cancellation_count += 1
                continue

            # Find the destination stop for delay calculation
            to_stop = None
            for stop in journey.stops:
                if stop.station_code == to_station:
                    to_stop = stop
                    break

            if to_stop and to_stop.actual_arrival and to_stop.scheduled_arrival:
                delay = (
                    to_stop.actual_arrival - to_stop.scheduled_arrival
                ).total_seconds() / 60
                delay = max(0, delay)
                total_delay += delay
                if delay <= 5:
                    on_time_count += 1
            else:
                # No arrival data, assume on time
                on_time_count += 1

        return CarrierRouteStats(
            carrier_name=carrier_name,
            train_count=len(journeys),
            on_time_count=on_time_count,
            cancellation_count=cancellation_count,
            total_delay_minutes=total_delay,
        )

    def _format_carrier_description(self, stats: CarrierRouteStats) -> str:
        """Format a single carrier's statistics as a sentence fragment."""
        train_word = "train" if stats.train_count == 1 else "trains"

        # Base: "NJ Transit had 9 trains follow this route with 100% departing on time"
        desc = (
            f"there were {stats.train_count} {stats.carrier_name} {train_word} on this route "
            f"with {stats.on_time_percentage:.0f}% departing on time"
        )

        # Add delay and/or cancellation info in parentheses if applicable
        extras = []
        if stats.non_cancelled_count > 0 and stats.average_delay_minutes >= 1:
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
        from_name = get_station_name(from_station)
        to_name = get_station_name(to_station)

        if not journeys:
            return OperationsSummary(
                headline=f"{from_name} to {to_name}: No data",
                body="No trains have completed this route in the past 90 minutes.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Group journeys by carrier
        njt_journeys = [j for j in journeys if j.data_source == "NJT"]
        amtrak_journeys = [j for j in journeys if j.data_source == "AMTRAK"]

        # Calculate stats for each carrier
        njt_stats = self._calculate_carrier_route_stats(njt_journeys, to_station)
        amtrak_stats = self._calculate_carrier_route_stats(amtrak_journeys, to_station)

        # Build carrier descriptions
        carrier_descriptions = []
        if njt_stats:
            carrier_descriptions.append(self._format_carrier_description(njt_stats))
        if amtrak_stats:
            carrier_descriptions.append(self._format_carrier_description(amtrak_stats))

        # Build body text
        if len(carrier_descriptions) == 1:
            body = f"Over the past 90 minutes, {carrier_descriptions[0]}."
        else:
            # Join with period and space for multiple carriers
            body = f"Over the past 90 minutes, {carrier_descriptions[0]}. {carrier_descriptions[1]}."

        # Calculate aggregate metrics for the response
        total_trains = len(journeys)
        total_on_time = (njt_stats.on_time_count if njt_stats else 0) + (
            amtrak_stats.on_time_count if amtrak_stats else 0
        )
        total_cancellations = (njt_stats.cancellation_count if njt_stats else 0) + (
            amtrak_stats.cancellation_count if amtrak_stats else 0
        )
        total_delay = (njt_stats.total_delay_minutes if njt_stats else 0) + (
            amtrak_stats.total_delay_minutes if amtrak_stats else 0
        )

        non_cancelled = total_trains - total_cancellations
        on_time_pct = (total_on_time / non_cancelled * 100) if non_cancelled > 0 else 0
        avg_delay = total_delay / non_cancelled if non_cancelled > 0 else 0

        # Generate headline (still useful for other contexts like network view)
        headline = f"{from_name} to {to_name}: {on_time_pct:.0f}% on time"

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="route",
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

    def _calculate_on_time_stats(
        self,
        journeys: list[TrainJourney],
        to_station: str | None = None,
    ) -> tuple[float, float, int]:
        """
        Calculate on-time percentage and average delay for a list of journeys.

        Args:
            journeys: List of journeys to analyze
            to_station: If provided, calculate delay at this station instead of final stop

        Returns:
            Tuple of (on_time_percentage, average_delay_minutes, sample_count)
        """
        on_time_count = 0
        total_delay = 0.0
        delay_samples = 0

        for journey in journeys:
            if journey.is_cancelled:
                continue

            if not journey.stops:
                continue

            # Find the stop to measure delay at
            if to_station:
                target_stop = next(
                    (s for s in journey.stops if s.station_code == to_station), None
                )
            else:
                target_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)

            if target_stop and target_stop.actual_arrival and target_stop.scheduled_arrival:
                delay = (
                    target_stop.actual_arrival - target_stop.scheduled_arrival
                ).total_seconds() / 60
                delay = max(0, delay)
                total_delay += delay
                delay_samples += 1
                if delay <= 5:
                    on_time_count += 1

        if delay_samples == 0:
            return 0.0, 0.0, 0

        on_time_pct = (on_time_count / delay_samples) * 100
        avg_delay = total_delay / delay_samples
        return on_time_pct, avg_delay, delay_samples

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
        # Calculate stats for similar trains (past 90 minutes)
        similar_on_time_pct, similar_avg_delay, similar_count = self._calculate_on_time_stats(
            similar_journeys, to_station
        )

        # Calculate stats for this specific train (historical)
        train_on_time_pct, train_avg_delay, train_count = self._calculate_on_time_stats(
            train_journeys, to_station
        )

        has_similar_data = similar_count > 0
        has_train_data = train_count > 0
        carrier_name = "NJ Transit" if data_source == "NJT" else "Amtrak" if data_source else None

        # Generate headline
        headline_parts = []

        if has_similar_data:
            headline = f"Recent departures: {similar_on_time_pct:.0f}% on time"
        else:
            headline = "View On-Time Stats"

        # Generate body
        body_parts = []

        if has_similar_data and carrier_name:
            similar_text = (
                f"There were {similar_count} similar {carrier_name} "
                f"train{'s' if similar_count != 1 else ''} in the past 90 minutes and "
                f"{similar_on_time_pct:.0f}% departed on-time"
            )
            if similar_avg_delay >= 1:
                similar_text += f" ({similar_avg_delay:.0f} min avg delay)"
            similar_text += "."
            body_parts.append(similar_text)

        if has_train_data:
            train_text = (
                f"Train {train_id} historically departs on time "
                f"{train_on_time_pct:.0f}% of the time"
            )
            if train_avg_delay >= 1:
                train_text += f" ({train_avg_delay:.0f} min avg delay)"
            train_text += "."
            body_parts.append(train_text)

        if not body_parts:
            body_parts.append(f"No performance data available for Train {train_id}.")

        body = " ".join(body_parts)

        # Use train stats for metrics if available, otherwise similar trains
        if has_train_data:
            metrics = SummaryMetrics(
                on_time_percentage=train_on_time_pct,
                average_delay_minutes=train_avg_delay,
                train_count=train_count,
            )
        elif has_similar_data:
            metrics = SummaryMetrics(
                on_time_percentage=similar_on_time_pct,
                average_delay_minutes=similar_avg_delay,
                train_count=similar_count,
            )
        else:
            metrics = None

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="train",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=now_et(),
            metrics=metrics,
        )
