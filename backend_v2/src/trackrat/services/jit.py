"""
Just-in-Time (JIT) update service for TrackRat V2.

Ensures data freshness when users request train information.
"""

from datetime import date
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.collectors.bart.collector import BARTCollector
from trackrat.collectors.lirr.collector import LIRRCollector
from trackrat.collectors.mbta.collector import MBTACollector
from trackrat.collectors.metra.collector import MetraCollector
from trackrat.collectors.mnr.collector import MNRCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.subway.collector import SubwayCollector
from trackrat.collectors.wmata.collector import WMATACollector
from trackrat.db.engine import retry_on_deadlock
from trackrat.models.database import TrainJourney
from trackrat.settings import get_settings
from trackrat.utils.time import is_stale, now_et, safe_datetime_subtract

logger = get_logger(__name__)


class JustInTimeUpdateService:
    """Updates train data on-demand to ensure freshness."""

    def __init__(self, njt_client: NJTransitClient | None = None) -> None:
        """Initialize the JIT update service.

        Args:
            njt_client: Optional NJ Transit client instance
        """
        self.settings = get_settings()
        self.njt_client = njt_client
        self._njt_collector: JourneyCollector | None = None
        self._amtrak_collector: AmtrakJourneyCollector | None = None
        self._path_collector: PathCollector | None = None
        self._lirr_collector: LIRRCollector | None = None
        self._mnr_collector: MNRCollector | None = None
        self._subway_collector: SubwayCollector | None = None
        self._metra_collector: MetraCollector | None = None
        self._wmata_collector: WMATACollector | None = None
        self._bart_collector: BARTCollector | None = None
        self._mbta_collector: MBTACollector | None = None

    async def __aenter__(self) -> "JustInTimeUpdateService":
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit async context and clean up resources."""
        if self._path_collector:
            await self._path_collector.close()
            self._path_collector = None
        if self._lirr_collector:
            await self._lirr_collector.client.close()
            self._lirr_collector = None
        if self._mnr_collector:
            await self._mnr_collector.client.close()
            self._mnr_collector = None
        if self._subway_collector:
            await self._subway_collector.client.close()
            self._subway_collector = None
        if self._metra_collector:
            await self._metra_collector.client.close()
            self._metra_collector = None
        if self._wmata_collector and self._wmata_collector.client:
            await self._wmata_collector.client.close()
            self._wmata_collector = None
        if self._bart_collector:
            await self._bart_collector.client.close()
            self._bart_collector = None
        if self._mbta_collector:
            await self._mbta_collector.close()
            self._mbta_collector = None
        # AmtrakJourneyCollector doesn't have a close method - no cleanup needed
        self._amtrak_collector = None

    @property
    def njt_collector(self) -> JourneyCollector:
        """Get or create NJT journey collector."""
        if self._njt_collector is None:
            if not self.njt_client:
                raise ValueError("NJT client required for NJT trains")
            self._njt_collector = JourneyCollector(self.njt_client)
        return self._njt_collector

    @property
    def amtrak_collector(self) -> AmtrakJourneyCollector:
        """Get or create Amtrak journey collector."""
        if self._amtrak_collector is None:
            self._amtrak_collector = AmtrakJourneyCollector()
        return self._amtrak_collector

    @property
    def path_collector(self) -> PathCollector:
        """Get or create PATH journey collector."""
        if self._path_collector is None:
            self._path_collector = PathCollector()
        return self._path_collector

    @property
    def lirr_collector(self) -> LIRRCollector:
        """Get or create LIRR journey collector."""
        if self._lirr_collector is None:
            self._lirr_collector = LIRRCollector()
        return self._lirr_collector

    @property
    def mnr_collector(self) -> MNRCollector:
        """Get or create Metro-North journey collector."""
        if self._mnr_collector is None:
            self._mnr_collector = MNRCollector()
        return self._mnr_collector

    @property
    def subway_collector(self) -> SubwayCollector:
        """Get or create Subway journey collector."""
        if self._subway_collector is None:
            self._subway_collector = SubwayCollector()
        return self._subway_collector

    @property
    def metra_collector(self) -> MetraCollector:
        """Get or create Metra journey collector."""
        if self._metra_collector is None:
            self._metra_collector = MetraCollector()
        return self._metra_collector

    @property
    def wmata_collector(self) -> WMATACollector:
        """Get or create WMATA journey collector."""
        if self._wmata_collector is None:
            self._wmata_collector = WMATACollector()
        return self._wmata_collector

    @property
    def bart_collector(self) -> BARTCollector:
        """Get or create BART journey collector."""
        if self._bart_collector is None:
            self._bart_collector = BARTCollector()
        return self._bart_collector

    @property
    def mbta_collector(self) -> MBTACollector:
        """Get or create MBTA journey collector."""
        if self._mbta_collector is None:
            self._mbta_collector = MBTACollector()
        return self._mbta_collector

    async def get_collector_for_journey(
        self, journey: TrainJourney
    ) -> (
        JourneyCollector
        | AmtrakJourneyCollector
        | PathCollector
        | LIRRCollector
        | MetraCollector
        | MNRCollector
        | SubwayCollector
        | WMATACollector
        | BARTCollector
        | MBTACollector
        | None
    ):
        """Get the appropriate collector for a journey based on its data source.

        Args:
            journey: The train journey

        Returns:
            The appropriate collector for the journey's data source,
            or None for schedule-only sources (PATCO) that don't support JIT refresh
        """
        if journey.data_source == "NJT":
            return self.njt_collector
        elif journey.data_source == "AMTRAK":
            return self.amtrak_collector
        elif journey.data_source == "PATH":
            return self.path_collector
        elif journey.data_source == "LIRR":
            return self.lirr_collector
        elif journey.data_source == "MNR":
            return self.mnr_collector
        elif journey.data_source == "SUBWAY":
            return self.subway_collector
        elif journey.data_source == "METRA":
            return self.metra_collector
        elif journey.data_source == "WMATA":
            return self.wmata_collector
        elif journey.data_source == "BART":
            return self.bart_collector
        elif journey.data_source == "MBTA":
            return self.mbta_collector
        elif journey.data_source == "PATCO":
            # PATCO is schedule-only (GTFS static), no real-time API available
            return None
        else:
            raise ValueError(f"Unknown data source: {journey.data_source}")

    async def ensure_fresh_data(
        self,
        session: AsyncSession,
        train_id: str,
        journey_date: date | None = None,
        force_refresh: bool = False,
        data_source: str | None = None,
    ) -> TrainJourney | None:
        """Ensure train data is fresh, updating if necessary.

        Args:
            session: Database session
            train_id: Train ID to check
            journey_date: Optional journey date (defaults to today)
            force_refresh: Force a refresh regardless of staleness
            data_source: Optional data source filter (NJT, AMTRAK, PATH, PATCO)

        Returns:
            Updated TrainJourney or None if not found
        """
        if journey_date is None:
            journey_date = now_et().date()

        logger.info(
            "checking_data_freshness",
            train_id=train_id,
            journey_date=journey_date,
            force_refresh=force_refresh,
            data_source=data_source,
        )

        # Find the journey - eagerly load stops to avoid lazy loading issues
        # Build query conditions
        conditions = [
            TrainJourney.train_id == train_id,
            TrainJourney.journey_date == journey_date,
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        stmt = (
            select(TrainJourney)
            .where(and_(*conditions))
            .options(
                selectinload(TrainJourney.stops),
                # Load all delete-orphan collections to prevent
                # greenlet_spawn errors during flush orphan checks
                selectinload(TrainJourney.snapshots),
                selectinload(TrainJourney.segment_times),
                selectinload(TrainJourney.dwell_times),
                selectinload(TrainJourney.progress_snapshots),
            )
        )
        journey = await session.scalar(stmt)

        if not journey:
            logger.warning(
                "journey_not_found", train_id=train_id, journey_date=journey_date
            )
            # Could attempt discovery here, but for now return None
            return None

        # Check if data needs refresh
        needs_refresh = force_refresh or self.needs_refresh(journey)

        if needs_refresh:
            logger.info(
                "refreshing_journey_data",
                train_id=train_id,
                journey_id=journey.id,
                last_updated=(
                    journey.last_updated_at.isoformat()
                    if journey.last_updated_at
                    else None
                ),
                force_refresh=force_refresh,
            )

            try:
                # Wrap refresh in retry logic to handle deadlocks
                # After rollback, we must re-query the journey since ORM objects are detached
                async def do_refresh() -> TrainJourney | None:
                    # Re-query journey to get fresh state after potential rollback
                    fresh_journey = await session.scalar(stmt)
                    if not fresh_journey:
                        raise ValueError(
                            f"Journey {train_id} disappeared during refresh"
                        )
                    collector = await self.get_collector_for_journey(fresh_journey)
                    if collector is None:
                        # Schedule-only source (e.g., PATCO) - no JIT refresh available
                        return None
                    await collector.collect_journey_details(session, fresh_journey)
                    return fresh_journey

                refreshed = await retry_on_deadlock(session, do_refresh)

                if refreshed is None:
                    # Schedule-only source - no JIT refresh available
                    logger.debug(
                        "jit_refresh_not_available",
                        train_id=train_id,
                        data_source=journey.data_source,
                        reason="schedule-only data source",
                    )
                else:
                    logger.info(
                        "journey_data_refreshed",
                        train_id=train_id,
                        data_source=refreshed.data_source,
                        stops_count=refreshed.stops_count,
                        is_completed=refreshed.is_completed,
                    )
                    journey = refreshed

            except Exception as e:
                logger.error(
                    "failed_to_refresh_journey",
                    train_id=train_id,
                    journey_id=journey.id,
                    error=str(e) or repr(e),
                    error_type=type(e).__name__,
                )
                # Clear session error state (e.g., PendingRollbackError from failed
                # flush/commit) so subsequent operations on this session still work.
                try:
                    await session.rollback()
                except Exception:
                    # Session is unrecoverable after a failed rollback -- any
                    # further use would raise "flushed transaction was not
                    # rolled back before reuse".  Return None immediately.
                    return None
                # Re-query journey since rollback expires all ORM objects.
                # Without this, accessing journey.stops would trigger a lazy load
                # that fails with raise_on_sql.
                try:
                    journey = await session.scalar(stmt)
                    if not journey:
                        return None
                except Exception:
                    return None
        else:
            logger.debug(
                "journey_data_fresh",
                train_id=train_id,
                age_seconds=(
                    safe_datetime_subtract(
                        now_et(), journey.last_updated_at
                    ).total_seconds()
                    if journey.last_updated_at
                    else None
                ),
            )

        return journey

    # Data sources with high-frequency background collectors (every 4 min).
    # JIT refresh for these sources creates lock contention with negligible
    # freshness gain, so we use the collector interval as the staleness baseline.
    _HIGH_FREQ_COLLECTOR_SOURCES = {
        "PATH",
        "LIRR",
        "MNR",
        "SUBWAY",
        "METRA",
        "WMATA",
        "BART",
        "MBTA",
    }
    _HIGH_FREQ_STALENESS_SECONDS = 240  # 4 minutes, matches collector interval

    def needs_refresh(self, journey: TrainJourney) -> bool:
        """Determine if a journey needs a data refresh.

        Args:
            journey: Journey to check

        Returns:
            True if data should be refreshed
        """
        # Never refresh completed, cancelled, or expired journeys
        if journey.is_completed or journey.is_cancelled or journey.is_expired:
            return False

        # Always refresh if no complete journey data
        if not journey.has_complete_journey:
            return True

        # Check staleness
        if journey.last_updated_at is None:
            return True

        # High-frequency collector sources use longer staleness to avoid
        # lock contention between JIT and the background collector
        if journey.data_source in self._HIGH_FREQ_COLLECTOR_SOURCES:
            return is_stale(journey.last_updated_at, self._HIGH_FREQ_STALENESS_SECONDS)

        # Use tighter staleness for trains departing soon
        staleness_threshold = self.settings.data_staleness_seconds
        if journey.scheduled_departure:
            seconds_to_departure = safe_datetime_subtract(
                journey.scheduled_departure, now_et()
            ).total_seconds()
            if 0 < seconds_to_departure <= self.settings.hot_train_window_minutes * 60:
                staleness_threshold = self.settings.hot_data_staleness_seconds

        return is_stale(journey.last_updated_at, staleness_threshold)

    async def get_fresh_train(
        self,
        session: AsyncSession,
        train_id: str,
        journey_date: date | None = None,
        force_refresh: bool = False,
        data_source: str | None = None,
    ) -> TrainJourney | None:
        """Get a train with guaranteed fresh data.

        This is a convenience method that ensures data is fresh
        before returning the journey.

        Args:
            session: Database session
            train_id: Train ID
            journey_date: Optional journey date
            force_refresh: Force refresh even if data seems fresh
            data_source: Optional data source filter (NJT, AMTRAK, PATH, PATCO)

        Returns:
            Fresh TrainJourney or None
        """
        journey = await self.ensure_fresh_data(
            session, train_id, journey_date, force_refresh, data_source
        )

        # Note: stops are already loaded via selectinload in ensure_fresh_data()
        # No need to refresh - that would cause a redundant database query
        return journey
