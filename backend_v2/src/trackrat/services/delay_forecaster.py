"""
Delay and cancellation forecaster service.

Uses hierarchical historical data to predict delays and cancellations.
Pattern follows HistoricalTrackPredictor with train_id -> line_code -> data_source fallbacks.

Supports both origin-level (TrainJourney) and stop-level (JourneyStop) queries.
When the user's boarding station differs from the train's origin, stop-level data
is tried first for more accurate station-specific predictions.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import ColumnElement, Row, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import SQLCoreOperations
from structlog import get_logger

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Configuration thresholds
MIN_TRAIN_ID_SAMPLES = 10
MIN_LINE_CODE_SAMPLES = 25
MIN_DATA_SOURCE_SAMPLES = 50

# Delay category thresholds (in minutes)
ON_TIME_THRESHOLD = 5
SLIGHT_DELAY_THRESHOLD = 15
SIGNIFICANT_DELAY_THRESHOLD = 30

# Historical lookback period (days)
HISTORICAL_LOOKBACK_DAYS = 365


@dataclass
class DelayStats:
    """Statistics for delay/cancellation at a given hierarchy level."""

    sample_count: int
    cancellation_count: int
    on_time_count: int
    slight_delay_count: int
    significant_delay_count: int
    major_delay_count: int
    total_delay_minutes: int
    level: str  # "train_id", "line_code", "data_source"


@dataclass
class DelayForecast:
    """Internal delay forecast result."""

    cancellation_probability: float
    on_time_probability: float
    slight_delay_probability: float
    significant_delay_probability: float
    major_delay_probability: float
    expected_delay_minutes: int
    confidence: Literal["high", "medium", "low"]
    sample_count: int
    factors: list[str]


class DelayForecaster:
    """
    Delay and cancellation forecaster using historical patterns.

    Hierarchical approach:
    1. Stop-level stats at user's boarding station (if different from origin)
       a. train_id at stop (>= 10 records)
       b. line_code at stop (>= 25 records)
       c. data_source at stop (>= 250 records)
    2. Origin-level stats (existing behavior)
       a. train_id at origin (>= 10 records)
       b. line_code at origin (>= 25 records)
       c. data_source at origin (>= 250 records)
    3. Static fallback

    Then apply hour/day-of-week adjustment and live congestion multiplier.
    """

    def __init__(self) -> None:
        """Initialize the forecaster."""
        self.congestion_analyzer = CongestionAnalyzer()

    @staticmethod
    def _delay_stats_columns(
        actual_dep: SQLCoreOperations[Any],
        scheduled_dep: SQLCoreOperations[Any],
        count_col: SQLCoreOperations[Any],
        is_cancelled: SQLCoreOperations[Any],
    ) -> list[ColumnElement[Any]]:
        """Build column expressions for delay statistics queries.

        Parameterized to work with both TrainJourney (origin-level)
        and JourneyStop (stop-level) columns.
        """
        delay_secs = func.extract("epoch", actual_dep) - func.extract(
            "epoch", scheduled_dep
        )
        has_times = and_(
            is_cancelled.is_not(True),
            actual_dep.is_not(None),
            scheduled_dep.is_not(None),
        )

        return [
            func.count(count_col).label("total"),
            func.count(count_col).filter(is_cancelled.is_(True)).label("cancelled"),
            func.count(count_col)
            .filter(and_(has_times, delay_secs <= ON_TIME_THRESHOLD * 60))
            .label("on_time"),
            func.count(count_col)
            .filter(
                and_(
                    has_times,
                    delay_secs > ON_TIME_THRESHOLD * 60,
                    delay_secs <= SLIGHT_DELAY_THRESHOLD * 60,
                )
            )
            .label("slight"),
            func.count(count_col)
            .filter(
                and_(
                    has_times,
                    delay_secs > SLIGHT_DELAY_THRESHOLD * 60,
                    delay_secs <= SIGNIFICANT_DELAY_THRESHOLD * 60,
                )
            )
            .label("significant"),
            func.count(count_col)
            .filter(and_(has_times, delay_secs > SIGNIFICANT_DELAY_THRESHOLD * 60))
            .label("major"),
            func.sum(
                case(
                    (has_times, func.greatest(0, delay_secs / 60)),
                    else_=0,
                )
            ).label("total_delay"),
        ]

    @staticmethod
    def _row_to_delay_stats(row: Row[Any] | None, level: str) -> DelayStats | None:
        """Convert a query result row to DelayStats."""
        if not row or row.total == 0:
            return None
        return DelayStats(
            sample_count=row.total,
            cancellation_count=row.cancelled or 0,
            on_time_count=row.on_time or 0,
            slight_delay_count=row.slight or 0,
            significant_delay_count=row.significant or 0,
            major_delay_count=row.major or 0,
            total_delay_minutes=int(row.total_delay or 0),
            level=level,
        )

    async def forecast(
        self,
        train_id: str,
        station_code: str,
        origin_station_code: str,
        line_code: str | None,
        data_source: str,
        journey_date: date,
        scheduled_departure: datetime,
        db: AsyncSession,
    ) -> DelayForecast:
        """
        Forecast delay and cancellation probability for a train.

        Args:
            train_id: Train identifier (e.g., '3427')
            station_code: User's boarding station code (e.g., 'NP', 'JAM')
            origin_station_code: Train's origin station code (e.g., 'NY')
            line_code: Line code (e.g., 'NE', 'Mo')
            data_source: Service provider ('NJT', 'AMTRAK', 'PATH', etc.)
            journey_date: Date of journey
            scheduled_departure: Scheduled departure time
            db: Database session

        Returns:
            DelayForecast with probabilities and metadata
        """
        logger.info(
            "delay_forecast_start",
            train_id=train_id,
            station_code=station_code,
            origin_station_code=origin_station_code,
            line_code=line_code,
            data_source=data_source,
        )

        factors: list[str] = []
        selected_stats: DelayStats | None = None

        # Phase 1: Stop-level stats (only for mid-route stations)
        if station_code != origin_station_code:
            stats = await self._get_stop_train_id_stats(
                db, train_id, station_code, data_source
            )
            if stats and stats.sample_count >= MIN_TRAIN_ID_SAMPLES:
                selected_stats = stats
                factors.extend(["train_history", "stop_level"])
                logger.info(
                    "using_stop_train_id_stats",
                    train_id=train_id,
                    station_code=station_code,
                    samples=stats.sample_count,
                )

            if not selected_stats and line_code:
                stats = await self._get_stop_line_code_stats(
                    db, line_code, station_code, data_source
                )
                if stats and stats.sample_count >= MIN_LINE_CODE_SAMPLES:
                    selected_stats = stats
                    factors.extend(["line_pattern", "stop_level"])
                    logger.info(
                        "using_stop_line_code_stats",
                        line_code=line_code,
                        station_code=station_code,
                        samples=stats.sample_count,
                    )

            if not selected_stats:
                stats = await self._get_stop_data_source_stats(
                    db, station_code, data_source
                )
                if stats and stats.sample_count >= MIN_DATA_SOURCE_SAMPLES:
                    selected_stats = stats
                    factors.extend(["service_pattern", "stop_level"])
                    logger.info(
                        "using_stop_data_source_stats",
                        data_source=data_source,
                        station_code=station_code,
                        samples=stats.sample_count,
                    )

        # Phase 2: Origin-level stats
        if not selected_stats:
            stats = await self._get_train_id_stats(
                db, train_id, origin_station_code, data_source
            )
            if stats and stats.sample_count >= MIN_TRAIN_ID_SAMPLES:
                selected_stats = stats
                factors.append("train_history")
                logger.info(
                    "using_train_id_stats",
                    train_id=train_id,
                    samples=stats.sample_count,
                )

        if not selected_stats and line_code:
            stats = await self._get_line_code_stats(
                db, line_code, origin_station_code, data_source
            )
            if stats and stats.sample_count >= MIN_LINE_CODE_SAMPLES:
                selected_stats = stats
                factors.append("line_pattern")
                logger.info(
                    "using_line_code_stats",
                    line_code=line_code,
                    samples=stats.sample_count,
                )

        if not selected_stats:
            stats = await self._get_data_source_stats(
                db, origin_station_code, data_source
            )
            if stats and stats.sample_count >= MIN_DATA_SOURCE_SAMPLES:
                selected_stats = stats
                factors.append("service_pattern")
                logger.info(
                    "using_data_source_stats",
                    data_source=data_source,
                    samples=stats.sample_count,
                )

        # Phase 3: Static fallback
        if not selected_stats:
            logger.info(
                "using_static_fallback",
                train_id=train_id,
                data_source=data_source,
                reason="insufficient_historical_data",
            )
            return self._create_static_fallback(data_source)

        # Calculate base probabilities from historical stats
        forecast = self._calculate_probabilities(selected_stats)
        forecast.factors = factors

        # Apply hour/day-of-week adjustment (uses origin station for time patterns)
        hour_adjustment = await self._get_hour_day_adjustment(
            db,
            origin_station_code,
            data_source,
            scheduled_departure.hour,
            scheduled_departure.weekday(),
        )
        if hour_adjustment != 1.0:
            forecast = self._apply_adjustment(forecast, hour_adjustment)
            factors.append("time_pattern")

        # Apply live congestion multiplier (uses user's boarding station)
        congestion_multiplier = await self._get_congestion_multiplier(
            db, station_code, data_source
        )
        if congestion_multiplier > 1.0:
            forecast = self._apply_adjustment(forecast, congestion_multiplier)
            factors.append("live_congestion")
            logger.info(
                "applied_congestion_multiplier",
                multiplier=congestion_multiplier,
            )

        logger.info(
            "delay_forecast_complete",
            train_id=train_id,
            cancellation_prob=round(forecast.cancellation_probability, 3),
            on_time_prob=round(forecast.on_time_probability, 3),
            expected_delay=forecast.expected_delay_minutes,
            confidence=forecast.confidence,
            factors=factors,
        )

        return forecast

    # -------------------------------------------------------------------------
    # Origin-level query methods (query TrainJourney table)
    # -------------------------------------------------------------------------

    async def _get_train_id_stats(
        self,
        db: AsyncSession,
        train_id: str,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a specific train ID at its origin station."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            TrainJourney.actual_departure,
            TrainJourney.scheduled_departure,
            TrainJourney.id,
            TrainJourney.is_cancelled,
        )
        query = select(*cols).where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.origin_station_code == station_code,
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= cutoff_date,
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "train_id")

    async def _get_line_code_stats(
        self,
        db: AsyncSession,
        line_code: str,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a line code at an origin station."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            TrainJourney.actual_departure,
            TrainJourney.scheduled_departure,
            TrainJourney.id,
            TrainJourney.is_cancelled,
        )
        query = select(*cols).where(
            and_(
                TrainJourney.line_code == line_code,
                TrainJourney.origin_station_code == station_code,
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= cutoff_date,
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "line_code")

    async def _get_data_source_stats(
        self,
        db: AsyncSession,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a data source at an origin station."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            TrainJourney.actual_departure,
            TrainJourney.scheduled_departure,
            TrainJourney.id,
            TrainJourney.is_cancelled,
        )
        query = select(*cols).where(
            and_(
                TrainJourney.origin_station_code == station_code,
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= cutoff_date,
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "data_source")

    # -------------------------------------------------------------------------
    # Stop-level query methods (query JourneyStop joined to TrainJourney)
    # -------------------------------------------------------------------------

    async def _get_stop_train_id_stats(
        self,
        db: AsyncSession,
        train_id: str,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a specific train ID at a specific stop."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            JourneyStop.actual_departure,
            JourneyStop.scheduled_departure,
            JourneyStop.id,
            TrainJourney.is_cancelled,
        )
        query = (
            select(*cols)
            .select_from(JourneyStop)
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.train_id == train_id,
                    TrainJourney.data_source == data_source,
                    TrainJourney.journey_date >= cutoff_date,
                )
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "train_id")

    async def _get_stop_line_code_stats(
        self,
        db: AsyncSession,
        line_code: str,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a line code at a specific stop."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            JourneyStop.actual_departure,
            JourneyStop.scheduled_departure,
            JourneyStop.id,
            TrainJourney.is_cancelled,
        )
        query = (
            select(*cols)
            .select_from(JourneyStop)
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.line_code == line_code,
                    TrainJourney.data_source == data_source,
                    TrainJourney.journey_date >= cutoff_date,
                )
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "line_code")

    async def _get_stop_data_source_stats(
        self,
        db: AsyncSession,
        station_code: str,
        data_source: str,
    ) -> DelayStats | None:
        """Get delay stats for a data source at a specific stop."""
        cutoff_date = now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
        cols = self._delay_stats_columns(
            JourneyStop.actual_departure,
            JourneyStop.scheduled_departure,
            JourneyStop.id,
            TrainJourney.is_cancelled,
        )
        query = (
            select(*cols)
            .select_from(JourneyStop)
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.data_source == data_source,
                    TrainJourney.journey_date >= cutoff_date,
                )
            )
        )

        result = await db.execute(query)
        return self._row_to_delay_stats(result.one_or_none(), "data_source")

    # -------------------------------------------------------------------------
    # Adjustment methods
    # -------------------------------------------------------------------------

    async def _get_hour_day_adjustment(
        self,
        db: AsyncSession,
        station_code: str,
        data_source: str,
        hour: int,
        day_of_week: int,
    ) -> float:
        """
        Get adjustment multiplier based on hour and day of week.

        Compares delay rate at this hour/day vs overall average.
        Returns multiplier > 1.0 if delays are more common at this time.
        """
        cutoff_date = now_et().date() - timedelta(
            days=90
        )  # Use 90 days for time patterns

        # Get overall delay rate
        overall_query = select(
            func.count(TrainJourney.id).label("total"),
            func.count(TrainJourney.id)
            .filter(
                and_(
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.actual_departure.is_not(None),
                    TrainJourney.scheduled_departure.is_not(None),
                    func.extract("epoch", TrainJourney.actual_departure)
                    - func.extract("epoch", TrainJourney.scheduled_departure)
                    > ON_TIME_THRESHOLD * 60,
                )
            )
            .label("delayed"),
        ).where(
            and_(
                TrainJourney.origin_station_code == station_code,
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= cutoff_date,
            )
        )

        overall_result = await db.execute(overall_query)
        overall_row = overall_result.one_or_none()

        if not overall_row or overall_row.total < 100:
            return 1.0

        overall_delay_rate = overall_row.delayed / overall_row.total

        # Get delay rate at this hour/day
        hourday_query = select(
            func.count(TrainJourney.id).label("total"),
            func.count(TrainJourney.id)
            .filter(
                and_(
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.actual_departure.is_not(None),
                    TrainJourney.scheduled_departure.is_not(None),
                    func.extract("epoch", TrainJourney.actual_departure)
                    - func.extract("epoch", TrainJourney.scheduled_departure)
                    > ON_TIME_THRESHOLD * 60,
                )
            )
            .label("delayed"),
        ).where(
            and_(
                TrainJourney.origin_station_code == station_code,
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= cutoff_date,
                func.extract("hour", TrainJourney.scheduled_departure) == hour,
                func.extract("dow", TrainJourney.scheduled_departure) == day_of_week,
            )
        )

        hourday_result = await db.execute(hourday_query)
        hourday_row = hourday_result.one_or_none()

        if not hourday_row or hourday_row.total < 20:
            return 1.0

        hourday_delay_rate = hourday_row.delayed / hourday_row.total

        # Calculate adjustment (cap at 2.0 to prevent extreme values)
        if overall_delay_rate > 0:
            adjustment: float = min(
                2.0, max(0.5, hourday_delay_rate / overall_delay_rate)
            )
        else:
            adjustment = 1.0

        logger.debug(
            "hour_day_adjustment",
            hour=hour,
            day_of_week=day_of_week,
            overall_rate=round(overall_delay_rate, 3),
            hourday_rate=round(hourday_delay_rate, 3),
            adjustment=round(adjustment, 3),
        )

        return adjustment

    async def _get_congestion_multiplier(
        self,
        db: AsyncSession,
        station_code: str,
        data_source: str,
    ) -> float:
        """
        Get live congestion multiplier for a station.

        Uses the congestion analyzer to check current network conditions.
        """
        try:
            congestion_data = (
                await self.congestion_analyzer.get_network_congestion_optimized(
                    db, time_window_hours=2, data_source=data_source
                )
            )

            # Find segments departing from this station
            relevant_segments = [
                s for s in congestion_data if s.from_station == station_code
            ]

            if not relevant_segments:
                return 1.0

            # Average congestion factor across relevant segments
            avg_factor = sum(s.congestion_factor for s in relevant_segments) / len(
                relevant_segments
            )

            # Cap the multiplier to prevent extreme values
            return min(2.0, max(1.0, avg_factor))

        except Exception as e:
            logger.warning("congestion_multiplier_failed", error=str(e))
            return 1.0

    # -------------------------------------------------------------------------
    # Probability calculation and adjustment
    # -------------------------------------------------------------------------

    def _calculate_probabilities(self, stats: DelayStats) -> DelayForecast:
        """Calculate probabilities from delay stats."""
        total = stats.sample_count
        non_cancelled = total - stats.cancellation_count

        # Cancellation probability
        cancellation_prob = stats.cancellation_count / total if total > 0 else 0.0

        # Delay probabilities (among non-cancelled journeys)
        if non_cancelled > 0:
            on_time_prob = stats.on_time_count / non_cancelled
            slight_prob = stats.slight_delay_count / non_cancelled
            significant_prob = stats.significant_delay_count / non_cancelled
            major_prob = stats.major_delay_count / non_cancelled
        else:
            on_time_prob = 0.8
            slight_prob = 0.15
            significant_prob = 0.04
            major_prob = 0.01

        # Normalize to ensure they sum to 1.0
        delay_total = on_time_prob + slight_prob + significant_prob + major_prob
        if delay_total > 0:
            on_time_prob /= delay_total
            slight_prob /= delay_total
            significant_prob /= delay_total
            major_prob /= delay_total
        else:
            # Records exist but none have actual departure times yet;
            # use the same conservative defaults as the non_cancelled == 0 case
            on_time_prob = 0.8
            slight_prob = 0.15
            significant_prob = 0.04
            major_prob = 0.01

        # Expected delay (average of non-cancelled journeys)
        if non_cancelled > 0:
            expected_delay = int(stats.total_delay_minutes / non_cancelled)
        else:
            expected_delay = 0

        # Confidence based on sample count
        if stats.sample_count >= MIN_TRAIN_ID_SAMPLES:
            if stats.level == "train_id":
                confidence: Literal["high", "medium", "low"] = "high"
            elif stats.level == "line_code":
                confidence = "medium"
            else:
                confidence = "low"
        else:
            confidence = "low"

        return DelayForecast(
            cancellation_probability=cancellation_prob,
            on_time_probability=on_time_prob,
            slight_delay_probability=slight_prob,
            significant_delay_probability=significant_prob,
            major_delay_probability=major_prob,
            expected_delay_minutes=expected_delay,
            confidence=confidence,
            sample_count=stats.sample_count,
            factors=[],
        )

    def _apply_adjustment(
        self, forecast: DelayForecast, multiplier: float
    ) -> DelayForecast:
        """
        Apply adjustment multiplier to delay probabilities.

        Increases delay probabilities proportionally while keeping them normalized.
        """
        if multiplier <= 1.0:
            return forecast

        # Shift probability from on_time to delays proportionally
        shift_amount = forecast.on_time_probability * (multiplier - 1) * 0.5

        new_on_time = forecast.on_time_probability - shift_amount
        new_slight = forecast.slight_delay_probability + shift_amount * 0.5
        new_significant = forecast.significant_delay_probability + shift_amount * 0.3
        new_major = forecast.major_delay_probability + shift_amount * 0.2

        # Normalize
        total = new_on_time + new_slight + new_significant + new_major
        if total <= 0:
            return forecast
        new_on_time /= total
        new_slight /= total
        new_significant /= total
        new_major /= total

        # Apply minimum floor AFTER normalization, redistributing deficit to delay categories
        if new_on_time < 0.1:
            deficit = 0.1 - new_on_time
            new_on_time = 0.1
            delay_total = new_slight + new_significant + new_major
            if delay_total > 0:
                new_slight -= deficit * (new_slight / delay_total)
                new_significant -= deficit * (new_significant / delay_total)
                new_major -= deficit * (new_major / delay_total)

        # Adjust expected delay
        new_expected = int(forecast.expected_delay_minutes * multiplier)

        return DelayForecast(
            cancellation_probability=forecast.cancellation_probability,
            on_time_probability=new_on_time,
            slight_delay_probability=new_slight,
            significant_delay_probability=new_significant,
            major_delay_probability=new_major,
            expected_delay_minutes=new_expected,
            confidence=forecast.confidence,
            sample_count=forecast.sample_count,
            factors=forecast.factors,
        )

    def _create_static_fallback(self, data_source: str) -> DelayForecast:
        """Create static fallback when no historical data available."""
        # Conservative defaults based on general transit statistics
        if data_source == "AMTRAK":
            # Amtrak historically has slightly higher delay rates
            return DelayForecast(
                cancellation_probability=0.02,
                on_time_probability=0.70,
                slight_delay_probability=0.20,
                significant_delay_probability=0.07,
                major_delay_probability=0.03,
                expected_delay_minutes=8,
                confidence="low",
                sample_count=0,
                factors=["static_fallback"],
            )
        elif data_source == "PATH":
            # PATH is generally very reliable with frequent service
            return DelayForecast(
                cancellation_probability=0.01,
                on_time_probability=0.85,
                slight_delay_probability=0.10,
                significant_delay_probability=0.03,
                major_delay_probability=0.01,
                expected_delay_minutes=2,
                confidence="low",
                sample_count=0,
                factors=["static_fallback"],
            )
        else:
            # NJT defaults
            return DelayForecast(
                cancellation_probability=0.03,
                on_time_probability=0.75,
                slight_delay_probability=0.17,
                significant_delay_probability=0.06,
                major_delay_probability=0.02,
                expected_delay_minutes=5,
                confidence="low",
                sample_count=0,
                factors=["static_fallback"],
            )


# Singleton instance
delay_forecaster = DelayForecaster()
