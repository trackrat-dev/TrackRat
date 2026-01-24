"""
Just-in-Time (JIT) update service for TrackRat V2.

Ensures data freshness when users request train information.
"""

from datetime import date
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.collectors.lirr.collector import LIRRCollector
from trackrat.collectors.mnr.collector import MNRCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.collectors.path.collector import PathCollector
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

    async def get_collector_for_journey(
        self, journey: TrainJourney
    ) -> JourneyCollector | AmtrakJourneyCollector | PathCollector | LIRRCollector | MNRCollector:
        """Get the appropriate collector for a journey based on its data source.

        Args:
            journey: The train journey

        Returns:
            The appropriate collector for the journey's data source
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
        from sqlalchemy.orm import selectinload

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
                # Get appropriate collector for this journey
                collector = await self.get_collector_for_journey(journey)

                # Use collector to update journey
                await collector.collect_journey_details(session, journey)

                logger.info(
                    "journey_data_refreshed",
                    train_id=train_id,
                    data_source=journey.data_source,
                    stops_count=journey.stops_count,
                    is_completed=journey.is_completed,
                )

            except Exception as e:
                logger.error(
                    "failed_to_refresh_journey",
                    train_id=train_id,
                    journey_id=journey.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Return stale data rather than failing
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

    def needs_refresh(self, journey: TrainJourney) -> bool:
        """Determine if a journey needs a data refresh.

        Args:
            journey: Journey to check

        Returns:
            True if data should be refreshed
        """
        # Never refresh completed or cancelled journeys
        if journey.is_completed or journey.is_cancelled:
            return False

        # Always refresh if no complete journey data
        if not journey.has_complete_journey:
            return True

        # Check staleness
        if journey.last_updated_at is None:
            return True

        return is_stale(journey.last_updated_at, self.settings.data_staleness_seconds)

    async def ensure_fresh_departures(
        self,
        session: AsyncSession,
        journeys: list[TrainJourney],
        max_concurrent: int = 5,
    ) -> dict[int, bool]:
        """Ensure multiple journeys have fresh data.

        Args:
            session: Database session
            journeys: List of journeys to check
            max_concurrent: Maximum concurrent refreshes

        Returns:
            Dict mapping journey ID to refresh success status
        """

        results = {}

        # Group journeys by refresh need
        need_refresh = []
        for journey in journeys:
            if journey.id is None:
                continue  # Skip journeys without ID (shouldn't happen for persisted objects)
            if self.needs_refresh(journey):
                need_refresh.append(journey)
            else:
                results[journey.id] = True

        if not need_refresh:
            return results

        logger.info(
            "refreshing_multiple_journeys", count=len(need_refresh), total=len(journeys)
        )

        # Refresh in batches
        for i in range(0, len(need_refresh), max_concurrent):
            batch = need_refresh[i : i + max_concurrent]

            # Create refresh tasks
            tasks = []
            for journey in batch:
                if journey.id is None:
                    continue  # Skip journeys without ID
                task = self._refresh_journey_safe(session, journey)
                tasks.append((journey.id, task))

            # Wait for batch to complete
            for journey_id, task in tasks:
                try:
                    await task
                    results[journey_id] = True
                except Exception as e:
                    logger.error(
                        "batch_refresh_failed", journey_id=journey_id, error=str(e)
                    )
                    results[journey_id] = False

        return results

    async def _refresh_journey_safe(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Safely refresh a journey, catching exceptions.

        Args:
            session: Database session
            journey: Journey to refresh
        """
        try:
            collector = await self.get_collector_for_journey(journey)
            await collector.collect_journey_details(session, journey)
        except Exception as e:
            logger.error(
                "journey_refresh_failed",
                journey_id=journey.id,
                train_id=journey.train_id,
                data_source=journey.data_source,
                error=str(e),
            )
            raise

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
