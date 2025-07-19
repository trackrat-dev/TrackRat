"""
In-process scheduler service for TrackRat V2.

Uses APScheduler to run periodic tasks within the FastAPI application.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.config import Settings, get_settings
from trackrat.db.engine import get_session
from trackrat.models.database import TrainJourney
from trackrat.services.apns import SimpleAPNSService
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.time import (
    calculate_delay,
    ensure_timezone_aware,
    now_et,
    safe_datetime_subtract,
)

logger = get_logger(__name__)


class SchedulerService:
    """Manages scheduled tasks for data collection."""

    def __init__(
        self,
        settings: Settings | None = None,
        apns_service: SimpleAPNSService | None = None,
    ) -> None:
        """Initialize the scheduler service."""
        self.settings = settings or get_settings()
        self.apns_service = apns_service

        # Configure APScheduler with proper async executor
        from apscheduler.executors.asyncio import AsyncIOExecutor

        executors = {"default": AsyncIOExecutor()}

        job_defaults = {"coalesce": False, "max_instances": 1}

        self.scheduler = AsyncIOScheduler(
            executors=executors, job_defaults=job_defaults, timezone="America/New_York"
        )
        self.njt_client: NJTransitClient | None = None
        self.jit_service: JustInTimeUpdateService | None = None
        self._running_tasks: dict[str, asyncio.Task[Any]] = {}

    async def start(self) -> None:
        """Start the scheduler and configure jobs."""
        logger.info("starting_scheduler_service")

        # Initialize NJ Transit client
        self.njt_client = NJTransitClient(self.settings)

        # Initialize JIT service with the NJ Transit client
        self.jit_service = JustInTimeUpdateService(self.njt_client)

        # Schedule NJT discovery job
        self.scheduler.add_job(
            self.run_njt_discovery,
            trigger=IntervalTrigger(minutes=self.settings.discovery_interval_minutes),
            id="njt_train_discovery",
            name="NJT Train Discovery",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            misfire_grace_time=300,  # 5 minute grace period
        )

        # Schedule Amtrak discovery job - using same interval
        self.scheduler.add_job(
            self.run_amtrak_discovery,
            trigger=IntervalTrigger(minutes=self.settings.discovery_interval_minutes),
            id="amtrak_train_discovery",
            name="Amtrak Train Discovery",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )

        # Schedule journey collection check (every 5 minutes)
        # This checks for trains needing updates and schedules them
        self.scheduler.add_job(
            self.check_journey_updates,
            trigger=IntervalTrigger(minutes=5),
            id="journey_update_check",
            name="Journey Update Check",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule Live Activity updates (every minute)
        self.scheduler.add_job(
            self.update_live_activities,
            trigger=IntervalTrigger(minutes=1),
            id="live_activity_updates",
            name="Live Activity Updates",
            replace_existing=True,
            max_instances=1,
        )

        # Start the scheduler
        self.scheduler.start()

        # Run discovery immediately on startup
        asyncio.create_task(self.run_njt_discovery())
        asyncio.create_task(self.run_amtrak_discovery())

        logger.info(
            "scheduler_started", jobs=[job.id for job in self.scheduler.get_jobs()]
        )

    async def stop(self) -> None:
        """Stop the scheduler and cleanup."""
        logger.info("stopping_scheduler_service")

        # Cancel any running tasks
        for task_id, task in self._running_tasks.items():
            if not task.done():
                logger.info("cancelling_task", task_id=task_id)
                task.cancel()

        # Shutdown scheduler
        self.scheduler.shutdown(wait=True)

        # Close NJ Transit client
        if self.njt_client:
            await self.njt_client.close()

        logger.info("scheduler_stopped")

    async def run_njt_discovery(self) -> None:
        """Run NJ Transit train discovery for all configured stations."""
        task_id = f"njt_discovery_{now_et().isoformat()}"

        try:
            logger.info("starting_train_discovery_task")

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Run discovery
            if not self.njt_client:
                raise RuntimeError(
                    "NJTransitClient not initialized - call start() first"
                )
            collector = TrainDiscoveryCollector(self.njt_client)
            result = await collector.run()

            logger.info(
                "train_discovery_completed",
                total_discovered=result.get("total_discovered", 0),
                total_new=result.get("total_new", 0),
            )

            # Schedule batch collection for ALL discovered trains
            # This ensures all trains have their journey details collected
            if result.get("total_discovered", 0) > 0:
                await self.schedule_njt_batch_collection(result)

        except Exception as e:
            logger.error(
                "train_discovery_failed", error=str(e), error_type=type(e).__name__
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def run_amtrak_discovery(self) -> None:
        """Run Amtrak train discovery for trains serving NYP."""
        task_id = f"amtrak_discovery_{now_et().isoformat()}"

        try:
            logger.info("starting_amtrak_discovery_task")

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Run Amtrak discovery
            collector = AmtrakDiscoveryCollector()
            result = await collector.run()

            logger.info(
                "amtrak_discovery_completed",
                discovered_count=result.get("discovered_trains", 0),
            )

            # Clean up any conflicting jobs first
            await self.cleanup_conflicting_amtrak_jobs()

            # Schedule journey collection for discovered trains
            if result.get("discovered_trains", 0) > 0:
                await self.schedule_amtrak_journey_collections(
                    result.get("train_ids", [])
                )

        except Exception as e:
            logger.error(
                "amtrak_discovery_failed", error=str(e), error_type=type(e).__name__
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def check_journey_updates(self) -> None:
        """Check for trains needing journey updates."""
        task_id = f"journey_check_{now_et().isoformat()}"

        try:
            logger.info("checking_journey_updates")

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Find trains needing updates
            async with get_session() as session:
                # Trains that need initial collection (at departure time)
                await self.schedule_departure_collections(session)

                # Trains that need periodic updates (every 15 minutes)
                await self.schedule_periodic_updates(session)

        except Exception as e:
            logger.error(
                "journey_update_check_failed", error=str(e), error_type=type(e).__name__
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def schedule_departure_collections(self, session: AsyncSession) -> None:
        """Schedule collection for trains at their departure time."""
        # Look for trains departing in the next 10 minutes that haven't been collected
        window_start = now_et()
        window_end = window_start + timedelta(minutes=10)

        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.data_source == "NJT",
                TrainJourney.scheduled_departure >= window_start,
                TrainJourney.scheduled_departure <= window_end,
                TrainJourney.has_complete_journey.is_not(True),
                TrainJourney.is_cancelled.is_not(True),
            )
        )

        result = await session.execute(stmt)
        trains = result.scalars().all()

        for train in trains:
            # Schedule collection at departure time
            job_id = f"departure_collection_{train.train_id}_{train.journey_date}"

            # Check if job already exists
            if not self.scheduler.get_job(job_id) and train.scheduled_departure:
                self.scheduler.add_job(
                    self.collect_journey,
                    trigger=DateTrigger(
                        run_date=ensure_timezone_aware(train.scheduled_departure)
                    ),
                    args=[train.train_id, train.journey_date],
                    id=job_id,
                    name=f"Departure collection for {train.train_id}",
                    replace_existing=True,
                )

                logger.info(
                    "scheduled_departure_collection",
                    train_id=train.train_id,
                    departure_time=(
                        train.scheduled_departure.isoformat()
                        if train.scheduled_departure
                        else "unknown"
                    ),
                )

    async def schedule_periodic_updates(self, session: AsyncSession) -> None:
        """Schedule periodic updates for active trains."""
        # Find trains that need periodic updates
        cutoff_time = now_et() - timedelta(
            minutes=self.settings.journey_update_interval_minutes
        )

        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.has_complete_journey.is_(True),
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_expired.is_not(True),  # Exclude expired trains
                    TrainJourney.last_updated_at < cutoff_time,
                )
            )
            .limit(20)
        )  # Process in batches

        result = await session.execute(stmt)
        trains = result.scalars().all()

        for train in trains:
            # Use deterministic job ID to prevent duplicate updates
            job_id = f"periodic_update_{train.train_id}_{train.journey_date}"

            # Check if update job already exists
            if not self.scheduler.get_job(job_id):
                self.scheduler.add_job(
                    self.collect_journey,
                    trigger=DateTrigger(run_date=now_et()),
                    args=[train.train_id, train.journey_date],
                    id=job_id,
                    name=f"Periodic update for {train.train_id}",
                    replace_existing=True,
                    max_instances=1,  # Prevent overlapping instances
                )

            logger.info(
                "scheduled_periodic_update",
                train_id=train.train_id,
                last_updated=(
                    train.last_updated_at.isoformat()
                    if train.last_updated_at
                    else "unknown"
                ),
            )

    async def collect_journey(self, train_id: str, journey_date: datetime) -> None:
        """Collect journey data for a specific train."""
        task_id = f"journey_{train_id}_{now_et().isoformat()}"

        try:
            logger.info(
                "collecting_journey", train_id=train_id, journey_date=journey_date
            )

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Collect journey data
            if not self.njt_client:
                raise RuntimeError(
                    "NJTransitClient not initialized - call start() first"
                )
            collector = JourneyCollector(self.njt_client)
            result = await collector.collect_single_journey(train_id, journey_date)

            if result.get("success"):
                logger.info(
                    "journey_collection_completed",
                    train_id=train_id,
                    is_completed=result.get("is_completed", False),
                )
            else:
                logger.error(
                    "journey_collection_failed",
                    train_id=train_id,
                    error=result.get("error"),
                )

        except Exception as e:
            logger.error(
                "journey_collection_error",
                train_id=train_id,
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def schedule_new_train_collections(
        self, discovery_result: dict[str, Any]
    ) -> None:
        """Schedule initial collection for newly discovered trains."""
        async with get_session() as session:
            for station_result in discovery_result.get("station_results", {}).values():
                for train_id in station_result.get("new_train_ids", []):
                    # Get the journey record
                    stmt = select(TrainJourney).where(
                        and_(
                            TrainJourney.train_id == train_id,
                            TrainJourney.journey_date == now_et().date(),
                            TrainJourney.data_source == "NJT",
                        )
                    )
                    journey = await session.scalar(stmt)

                    if journey and journey.scheduled_departure:
                        # Ensure timezone-aware comparison
                        scheduled_tz = ensure_timezone_aware(
                            journey.scheduled_departure
                        )
                        current_time = now_et()

                        logger.debug(
                            "comparing_datetimes",
                            train_id=train_id,
                            scheduled_naive=journey.scheduled_departure,
                            scheduled_aware=scheduled_tz,
                            current_time=current_time,
                            scheduled_has_tz=journey.scheduled_departure.tzinfo
                            is not None,
                        )

                        if scheduled_tz > current_time:
                            # Schedule collection at departure time
                            job_id = (
                                f"initial_collection_{train_id}_{journey.journey_date}"
                            )

                            self.scheduler.add_job(
                                self.collect_journey,
                                trigger=DateTrigger(run_date=scheduled_tz),
                                args=[train_id, journey.journey_date],
                                id=job_id,
                                name=f"Initial collection for {train_id}",
                                replace_existing=True,
                            )

                            logger.info(
                                "scheduled_initial_collection",
                                train_id=train_id,
                                departure_time=(
                                    scheduled_tz.isoformat() if scheduled_tz else None
                                ),
                            )

    async def schedule_njt_batch_collection(
        self, discovery_result: dict[str, Any]
    ) -> None:
        """Schedule batch collection for all discovered NJ Transit trains.

        Args:
            discovery_result: Result from train discovery containing all train IDs
        """
        # Collect all train IDs from all stations
        all_train_ids = []
        for station_result in discovery_result.get("station_results", {}).values():
            # Get ALL train IDs from this station
            all_train_ids.extend(station_result.get("all_train_ids", []))

        if not all_train_ids:
            logger.debug("no_njt_trains_to_schedule")
            return

        # Remove duplicates (trains can appear at multiple stations)
        unique_train_ids = list(set(all_train_ids))

        logger.debug(
            "processing_njt_trains_for_collection",
            total_trains=len(all_train_ids),
            unique_trains=len(unique_train_ids),
        )

        # Filter trains that need collection
        trains_to_collect = []
        current_date = now_et().date()

        async with get_session() as session:
            for train_id in unique_train_ids:
                stmt = select(TrainJourney).where(
                    and_(
                        TrainJourney.train_id == train_id,
                        TrainJourney.journey_date == current_date,
                        TrainJourney.data_source == "NJT",
                    )
                )
                journey = await session.scalar(stmt)

                if journey:
                    # Collect if no complete journey data or data is stale (>15 minutes)
                    needs_collection = (
                        not journey.has_complete_journey
                        or journey.last_updated_at is None
                        or safe_datetime_subtract(
                            now_et(), journey.last_updated_at
                        ).total_seconds()
                        > 900
                    )

                    if needs_collection:
                        trains_to_collect.append(train_id)
                    else:
                        logger.debug(
                            "njt_journey_recently_updated",
                            train_id=train_id,
                            last_updated=journey.last_updated_at,
                        )

        if not trains_to_collect:
            logger.info(
                "no_njt_trains_need_collection", checked_count=len(unique_train_ids)
            )
            return

        # Schedule immediate batch collection
        job_id = f"njt_batch_collection_{now_et().isoformat()}"
        run_time = now_et() + timedelta(seconds=5)

        self.scheduler.add_job(
            self.collect_njt_journeys_batch,
            trigger=DateTrigger(run_date=run_time),
            args=[trains_to_collect],
            id=job_id,
            name=f"NJT batch collection ({len(trains_to_collect)} trains)",
            replace_existing=True,
            max_instances=1,
        )

        logger.info(
            "scheduled_njt_batch_collection",
            train_count=len(trains_to_collect),
            job_id=job_id,
            run_time=run_time.isoformat(),
        )

    async def schedule_amtrak_journey_collections(self, train_ids: list[str]) -> None:
        """Schedule journey collection for discovered Amtrak trains using batch processing.

        Args:
            train_ids: List of Amtrak train IDs to collect
        """
        if not train_ids:
            logger.debug("no_amtrak_trains_to_schedule")
            return

        # Process train IDs and create a deduplicated set based on train number
        unique_trains = {}
        for train_id in train_ids:
            train_num = train_id.split("-")[0] if "-" in train_id else train_id
            internal_train_id = f"A{train_num}"
            # Keep the first occurrence of each train number
            if internal_train_id not in unique_trains:
                unique_trains[internal_train_id] = train_id

        logger.debug(
            "deduplicating_amtrak_trains",
            original_count=len(train_ids),
            deduplicated_count=len(unique_trains),
        )

        # Filter out trains that already have journeys or collection jobs
        trains_to_collect = []
        current_date = now_et().date()

        async with get_session() as session:
            for internal_train_id, original_train_id in unique_trains.items():
                # Check if journey already exists
                stmt = select(TrainJourney).where(
                    and_(
                        TrainJourney.train_id == internal_train_id,
                        TrainJourney.journey_date == current_date,
                        TrainJourney.data_source == "AMTRAK",
                    )
                )
                existing_journey = await session.scalar(stmt)

                if not existing_journey:
                    trains_to_collect.append(original_train_id)
                else:
                    logger.debug(
                        "amtrak_journey_already_exists",
                        train_id=original_train_id,
                        internal_id=internal_train_id,
                    )

        if not trains_to_collect:
            logger.debug("no_new_amtrak_trains_to_collect")
            return

        # Create single batch collection job
        batch_job_id = f"amtrak_batch_collection_{current_date}"
        existing_batch_job = self.scheduler.get_job(batch_job_id)

        if not existing_batch_job:
            # Schedule batch collection with minimal delay
            run_time = now_et() + timedelta(seconds=5)

            self.scheduler.add_job(
                self.collect_all_amtrak_journeys_batch,
                trigger=DateTrigger(run_date=run_time),
                args=[trains_to_collect],
                id=batch_job_id,
                name=f"Amtrak batch collection ({len(trains_to_collect)} trains)",
                replace_existing=True,
                max_instances=1,
            )

            logger.info(
                "scheduled_amtrak_batch_collection",
                train_count=len(trains_to_collect),
                job_id=batch_job_id,
                run_time=run_time.isoformat(),
            )
        else:
            logger.debug(
                "amtrak_batch_collection_already_scheduled",
                job_id=batch_job_id,
                train_count=len(trains_to_collect),
            )

    async def collect_amtrak_journey(self, amtrak_train_id: str) -> None:
        """Collect journey data for a specific Amtrak train.

        NOTE: This method is deprecated in favor of batch processing via
        collect_all_amtrak_journeys_batch(). Individual collection is less
        efficient due to redundant API calls.

        Args:
            amtrak_train_id: Amtrak train ID (e.g., "2150-4")
        """
        task_id = f"amtrak_journey_{amtrak_train_id}_{now_et().isoformat()}"

        try:
            logger.info("collecting_amtrak_journey", train_id=amtrak_train_id)

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Import and collect journey data using Amtrak collector
            from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector

            collector = AmtrakJourneyCollector()
            journey = await collector.collect_journey(amtrak_train_id)

            if journey:
                logger.info(
                    "amtrak_journey_collection_completed",
                    train_id=amtrak_train_id,
                    internal_id=journey.train_id,
                    stops_count=journey.stops_count,
                )
            else:
                logger.error(
                    "amtrak_journey_collection_failed",
                    train_id=amtrak_train_id,
                    error="Collection returned None",
                )

        except Exception as e:
            logger.error(
                "amtrak_journey_collection_error",
                train_id=amtrak_train_id,
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def cleanup_conflicting_amtrak_jobs(self) -> None:
        """Clean up any conflicting Amtrak collection jobs with inconsistent IDs."""
        current_date = now_et().date()
        jobs_to_remove = []

        # Find jobs with old ID format that might conflict
        for job in self.scheduler.get_jobs():
            if job.id.startswith("amtrak_collection_") and str(current_date) in job.id:
                # Check if this uses the old format (train-instance_date instead of internal_date)
                id_parts = job.id.split("amtrak_collection_")[1].split("_")
                if len(id_parts) > 0 and "-" in id_parts[0]:
                    # This is an old-format job ID, mark for removal
                    jobs_to_remove.append(job.id)

        # Remove conflicting jobs
        for job_id in jobs_to_remove:
            try:
                self.scheduler.remove_job(job_id)
                logger.info("removed_conflicting_amtrak_job", job_id=job_id)
            except Exception as e:
                logger.warning(
                    "failed_to_remove_conflicting_job", job_id=job_id, error=str(e)
                )

    async def collect_all_amtrak_journeys_batch(self, train_ids: list[str]) -> None:
        """Collect journey data for all Amtrak trains in a single batch operation.

        This method replaces the individual train collection approach with efficient
        batch processing to minimize API calls and improve performance.

        Args:
            train_ids: List of Amtrak train IDs to collect
        """
        if not train_ids:
            logger.info("no_amtrak_trains_to_collect")
            return

        # Process train IDs and create a deduplicated set based on train number
        unique_trains = {}
        for train_id in train_ids:
            train_num = train_id.split("-")[0] if "-" in train_id else train_id
            internal_train_id = f"A{train_num}"
            # Keep the first occurrence of each train number
            if internal_train_id not in unique_trains:
                unique_trains[internal_train_id] = train_id

        logger.info(
            "starting_amtrak_batch_collection",
            original_count=len(train_ids),
            deduplicated_count=len(unique_trains),
            train_ids=list(unique_trains.keys()),
        )

        try:
            # Import here to avoid circular imports
            from trackrat.collectors.amtrak.client import AmtrakClient

            # Make single API call to get all train data
            async with AmtrakClient() as client:
                all_trains_data = await client.get_all_trains()

            logger.info(
                "amtrak_batch_api_call_completed",
                stations_count=len(all_trains_data),
                total_trains=sum(len(trains) for trains in all_trains_data.values()),
            )

            # Create a lookup map of train ID -> train data for efficient access
            train_data_map = {}
            for train_list in all_trains_data.values():
                for train_data in train_list:
                    train_data_map[train_data.trainID] = train_data

            # Filter to only trains we're interested in
            target_trains = []
            for internal_id, original_id in unique_trains.items():
                if original_id in train_data_map:
                    target_trains.append(
                        (internal_id, original_id, train_data_map[original_id])
                    )
                else:
                    logger.warning(
                        "amtrak_train_not_found_in_api",
                        internal_id=internal_id,
                        original_id=original_id,
                    )

            logger.info("amtrak_trains_found_for_collection", count=len(target_trains))

            # Process trains sequentially to avoid SQLite concurrency issues
            # This eliminates all database transaction conflicts
            all_results: list[Any] = []

            for i, (internal_id, original_id, train_data) in enumerate(target_trains):
                logger.debug(
                    "processing_amtrak_train_sequential",
                    train_number=i + 1,
                    total_trains=len(target_trains),
                    internal_id=internal_id,
                )

                try:
                    # Process each train sequentially
                    await self._collect_single_amtrak_journey_from_data(
                        internal_id, original_id, train_data
                    )
                    all_results.append(True)  # Success marker
                except Exception as e:
                    all_results.append(e)
                    logger.error(
                        "amtrak_sequential_collection_failed",
                        internal_id=internal_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                # Small delay between trains to be gentle on the database
                if i < len(target_trains) - 1:
                    await asyncio.sleep(0.05)

            # Process results
            results = all_results

            # Log results
            if results:
                success_count = 0
                error_count = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        error_count += 1
                        internal_id = target_trains[i][0]
                        logger.error(
                            "amtrak_batch_collection_task_failed",
                            internal_id=internal_id,
                            error=str(result),
                            error_type=type(result).__name__,
                        )
                    else:
                        success_count += 1

                logger.info(
                    "amtrak_batch_collection_completed",
                    total_trains=len(target_trains),
                    success_count=success_count,
                    error_count=error_count,
                )
            else:
                logger.warning("no_valid_amtrak_trains_found_for_collection")

        except Exception as e:
            logger.error(
                "amtrak_batch_collection_failed",
                error=str(e),
                error_type=type(e).__name__,
                train_count=len(unique_trains),
            )

    async def _collect_single_amtrak_journey_from_data(
        self, internal_train_id: str, original_train_id: str, train_data: Any
    ) -> None:
        """Collect a single Amtrak journey using pre-fetched train data.

        Args:
            internal_train_id: Internal train ID (e.g., "A2150")
            original_train_id: Original Amtrak train ID (e.g., "2150-4")
            train_data: Pre-fetched AmtrakTrainData object
        """
        from trackrat.utils.locks import with_train_lock
        from trackrat.utils.time import now_et

        journey_date = now_et().date().isoformat()

        try:
            # Use the same locking mechanism as individual collection
            result = await with_train_lock(
                internal_train_id,
                journey_date,
                self._collect_journey_from_data_locked,
                train_data,
            )

            if result:
                logger.info(
                    "amtrak_batch_journey_collected",
                    internal_id=internal_train_id,
                    original_id=original_train_id,
                    stops_count=result.stops_count,
                )
            else:
                logger.warning(
                    "amtrak_batch_journey_collection_failed",
                    internal_id=internal_train_id,
                    original_id=original_train_id,
                )

        except Exception as e:
            logger.error(
                "amtrak_batch_journey_collection_error",
                internal_id=internal_train_id,
                original_id=original_train_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _collect_journey_from_data_locked(
        self, train_data: Any
    ) -> "TrainJourney | None":
        """Collect journey from pre-fetched data with locking applied.

        Args:
            train_data: Pre-fetched AmtrakTrainData object

        Returns:
            TrainJourney object if successful, None if failed
        """
        from trackrat.db.engine import get_session

        # Sequential processing eliminates most concurrency issues, so simpler retry logic
        try:
            async with get_session() as session:
                from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector

                collector = AmtrakJourneyCollector()
                # Use the collector's conversion method directly with pre-fetched data
                journey = await collector._convert_to_journey(session, train_data)
                if journey:
                    await session.commit()
                    return journey
                return None
        except Exception as e:
            logger.error(
                "journey_conversion_locked_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    async def collect_njt_journeys_batch(self, train_ids: list[str]) -> None:
        """Collect journey data for multiple NJ Transit trains in batch.

        Args:
            train_ids: List of NJ Transit train IDs to collect
        """
        if not train_ids:
            logger.info("no_njt_trains_to_collect")
            return

        task_id = f"njt_batch_collection_{now_et().isoformat()}"

        try:
            logger.info(
                "starting_njt_batch_collection",
                train_count=len(train_ids),
                train_ids=train_ids[:10],  # Log first 10 for debugging
            )

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            # Initialize NJT client if needed
            if not self.njt_client:
                raise RuntimeError("NJTransitClient not initialized")

            # Process trains sequentially to avoid database conflicts
            success_count = 0
            error_count = 0

            # Create journey collector
            from trackrat.collectors.njt.journey import JourneyCollector

            collector = JourneyCollector(self.njt_client)

            for i, train_id in enumerate(train_ids):
                try:
                    logger.debug(
                        "collecting_njt_journey",
                        train_id=train_id,
                        progress=f"{i+1}/{len(train_ids)}",
                    )

                    # Collect journey details (skip enhancement for scheduled batch collection)
                    journey = await collector.collect_journey(
                        train_id, skip_enhancement=True
                    )

                    if journey:
                        success_count += 1
                        logger.debug(
                            "njt_journey_collected",
                            train_id=train_id,
                            stops_count=journey.stops_count,
                        )
                    else:
                        error_count += 1
                        logger.warning(
                            "njt_journey_not_found",
                            train_id=train_id,
                        )

                    # Small delay between trains to be gentle on the API/database
                    if i < len(train_ids) - 1:
                        await asyncio.sleep(0.1)

                except Exception as e:
                    error_count += 1
                    logger.error(
                        "njt_journey_collection_failed",
                        train_id=train_id,
                        error=str(e),
                        error_type=type(e).__name__,
                        is_client_error="Client not initialized" in str(e),
                    )

            logger.info(
                "njt_batch_collection_completed",
                total_trains=len(train_ids),
                success_count=success_count,
                error_count=error_count,
            )

        except Exception as e:
            logger.error(
                "njt_batch_collection_error",
                error=str(e),
                error_type=type(e).__name__,
                train_count=len(train_ids),
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    async def update_live_activities(self) -> None:
        """Update all active Live Activities with current train data."""
        task_id = f"live_activity_update_{now_et().isoformat()}"

        try:
            logger.info("starting_live_activity_updates")

            # Track running task
            task = asyncio.current_task()
            if task:
                self._running_tasks[task_id] = task

            from sqlalchemy import and_, create_engine, select
            from sqlalchemy.orm import selectinload, sessionmaker

            from trackrat.models.database import LiveActivityToken, TrainJourney

            # Use synchronous database access to avoid greenlet issues in scheduler context
            # This is a workaround for APScheduler's async executor not properly initializing greenlets
            db_url = str(self.settings.database_url).replace(
                "sqlite+aiosqlite", "sqlite"
            )
            sync_engine = create_engine(
                db_url, connect_args={"check_same_thread": False}
            )
            SyncSession = sessionmaker(sync_engine)

            with SyncSession() as session:
                # Get active tokens that haven't expired
                stmt = select(LiveActivityToken).where(
                    and_(
                        LiveActivityToken.is_active.is_(True),
                        LiveActivityToken.expires_at > now_et(),
                    )
                )
                # Use synchronous query execution
                result = session.execute(stmt)
                active_tokens = list(result.scalars())

                if not active_tokens:
                    logger.debug("no_active_live_activity_tokens")
                    return

                # Group by train number for efficiency
                trains_to_update: dict[str, list[Any]] = {}
                for token in active_tokens:
                    if (
                        token.train_number
                        and token.train_number not in trains_to_update
                    ):
                        trains_to_update[token.train_number] = []
                    if token.train_number:
                        trains_to_update[token.train_number].append(token)

                logger.info(
                    "live_activity_tokens_found",
                    token_count=len(active_tokens),
                    train_count=len(trains_to_update),
                )

                # Check if APNS service is available
                if not self.apns_service:
                    logger.warning(
                        "apns_service_not_available",
                        reason="Service not initialized during startup",
                    )
                    return

                # Update each train's Live Activities
                for train_number, tokens in trains_to_update.items():
                    # Get latest journey for this train
                    journey_stmt = (
                        select(TrainJourney)
                        .where(
                            and_(
                                TrainJourney.train_id == train_number,
                                TrainJourney.journey_date == now_et().date(),
                            )
                        )
                        .options(selectinload(TrainJourney.stops))
                    )

                    journey = session.scalar(journey_stmt)

                    if not journey:
                        logger.warning(
                            "journey_not_found_for_live_activity",
                            train_number=train_number,
                        )
                        continue

                    # Check if journey data is stale (>60 seconds old)
                    if journey.last_updated_at is None or self._is_stale(
                        journey.last_updated_at
                    ):
                        logger.info(
                            "live_activity_journey_stale",
                            train_number=train_number,
                            last_updated=(
                                journey.last_updated_at.isoformat()
                                if journey.last_updated_at
                                else None
                            ),
                        )

                        # Refresh the data using JIT service
                        if self.jit_service:
                            try:
                                # Create an async session for the JIT service
                                async with get_session() as jit_session:
                                    refreshed_journey = (
                                        await self.jit_service.ensure_fresh_data(
                                            jit_session,
                                            train_number,
                                            journey.journey_date,
                                            force_refresh=True,
                                        )
                                    )

                                    if refreshed_journey:
                                        # Re-query in our session to get the updated data
                                        session.refresh(journey)
                                        # Re-load stops with the refreshed data
                                        refreshed_journey_obj = session.scalar(
                                            journey_stmt
                                        )
                                        if refreshed_journey_obj:
                                            journey = refreshed_journey_obj
                                            logger.info(
                                                "live_activity_journey_refreshed",
                                                train_number=train_number,
                                                new_last_updated=(
                                                    journey.last_updated_at.isoformat()
                                                    if journey.last_updated_at
                                                    else None
                                                ),
                                            )
                            except Exception as e:
                                logger.warning(
                                    "live_activity_refresh_failed",
                                    train_number=train_number,
                                    error=str(e),
                                    error_type=type(e).__name__,
                                )
                                # Continue with stale data rather than failing

                    # Calculate simple progress
                    current_stop = None
                    next_stop = None
                    journey_progress = 0.0
                    calculated_delay = 0  # Default delay

                    if journey and journey.stops:
                        # Sort stops by sequence to ensure proper ordering
                        sorted_stops = sorted(
                            journey.stops, key=lambda s: s.stop_sequence or 0
                        )

                        # Find user's origin and destination indices
                        origin_index = None
                        destination_index = None
                        for i, stop in enumerate(sorted_stops):
                            if stop.station_code == token.origin_code:
                                origin_index = i
                            if stop.station_code == token.destination_code:
                                destination_index = i

                        # If we found both, filter stops to user's journey
                        if origin_index is not None and destination_index is not None:
                            # Filter to only the user's journey segment
                            user_journey_stops = sorted_stops[
                                origin_index : destination_index + 1
                            ]

                            # Log stop sequence for debugging
                            stop_sequence_info = [
                                (
                                    s.stop_sequence,
                                    s.station_code,
                                    s.has_departed_station,
                                )
                                for s in user_journey_stops[:5]
                            ]  # First 5 stops
                            logger.debug(
                                "user_journey_stops_debug",
                                train_number=train_number,
                                origin_code=token.origin_code,
                                destination_code=token.destination_code,
                                user_journey_stop_count=len(user_journey_stops),
                                total_stop_count=len(sorted_stops),
                                first_stops=stop_sequence_info,
                            )

                            # Calculate progress based on user's journey only
                            total_user_stops = len(user_journey_stops)
                            departed_user_stops = sum(
                                1
                                for stop in user_journey_stops
                                if stop.has_departed_station
                            )
                            journey_progress = (
                                departed_user_stops / total_user_stops
                                if total_user_stops > 0
                                else 0.0
                            )

                            # Find current and next stops within user's journey
                            origin_station = user_journey_stops[0]
                            has_departed_origin = origin_station.has_departed_station

                            if not has_departed_origin:
                                # Train hasn't left origin yet - stay at origin for both current and next
                                current_stop = origin_station
                                next_stop = origin_station
                                logger.debug(
                                    "user_journey_at_origin",
                                    train_number=train_number,
                                    origin_stop=current_stop.station_name,
                                    origin_stop_sequence=current_stop.stop_sequence,
                                    user_journey_stops=total_user_stops,
                                )
                            else:
                                # Train has departed origin - find progression through journey
                                for i, stop in enumerate(user_journey_stops):
                                    if not stop.has_departed_station and i > 0:
                                        current_stop = user_journey_stops[i - 1]
                                        next_stop = stop
                                        # Log the stop sequence for debugging
                                        logger.debug(
                                            "user_journey_next_stop_found",
                                            train_number=train_number,
                                            current_stop=current_stop.station_name,
                                            current_stop_sequence=current_stop.stop_sequence,
                                            next_stop=next_stop.station_name,
                                            next_stop_sequence=next_stop.stop_sequence,
                                            user_journey_stops=total_user_stops,
                                            stop_index=i,
                                        )
                                        break
                        else:
                            # Fallback to all stops if we can't find origin/destination
                            logger.warning(
                                "origin_destination_not_found",
                                train_number=train_number,
                                origin_code=token.origin_code,
                                destination_code=token.destination_code,
                                available_stops=[s.station_code for s in sorted_stops],
                            )
                            total_stops = len(sorted_stops)
                            departed_stops = sum(
                                1 for stop in sorted_stops if stop.has_departed_station
                            )
                            journey_progress = (
                                departed_stops / total_stops if total_stops > 0 else 0.0
                            )

                    # Calculate delay from stops (similar to API logic)
                    if journey and journey.stops:
                        # Find the most recent departed stop with timing info
                        stops_for_delay = (
                            sorted_stops
                            if "sorted_stops" in locals()
                            else sorted(
                                journey.stops, key=lambda s: s.stop_sequence or 0
                            )
                        )
                        for stop in reversed(stops_for_delay):
                            if stop.has_departed_station:
                                if stop.actual_departure and stop.scheduled_departure:
                                    calculated_delay = calculate_delay(
                                        stop.scheduled_departure, stop.actual_departure
                                    )
                                    break
                                elif stop.actual_arrival and stop.scheduled_arrival:
                                    calculated_delay = calculate_delay(
                                        stop.scheduled_arrival, stop.actual_arrival
                                    )
                                    break

                    # Determine if train has departed from user's origin
                    has_train_departed = False
                    scheduled_departure_time = None
                    scheduled_arrival_time = None
                    next_stop_arrival_time = None

                    # Find the user's origin and destination stops
                    origin_stop = None
                    destination_stop = None

                    # Use sorted_stops if available, otherwise sort journey.stops
                    stops_to_check = (
                        sorted_stops
                        if "sorted_stops" in locals()
                        else (
                            sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
                            if journey and journey.stops
                            else []
                        )
                    )

                    for stop in stops_to_check:
                        if stop.station_code == token.origin_code:
                            origin_stop = stop
                            # Convert to ISO8601 string for iOS
                            scheduled_departure_time = (
                                stop.scheduled_departure.isoformat()
                                if stop.scheduled_departure
                                else None
                            )
                            # Check if departed

                            if stop.actual_departure:
                                has_train_departed = True
                            elif stop.scheduled_departure:
                                # Use ensure_timezone_aware to properly handle timezone conversion
                                scheduled_dep = ensure_timezone_aware(
                                    stop.scheduled_departure
                                )
                                current_time = now_et()
                                if scheduled_dep < current_time:
                                    has_train_departed = True
                        if stop.station_code == token.destination_code:
                            destination_stop = stop
                            # Convert to ISO8601 string for iOS
                            scheduled_arrival_time = (
                                stop.scheduled_arrival.isoformat()
                                if stop.scheduled_arrival
                                else None
                            )

                    # Get next stop arrival time
                    if next_stop:
                        # Convert to ISO8601 string for iOS
                        next_stop_arrival_time = (
                            next_stop.scheduled_arrival.isoformat()
                            if next_stop.scheduled_arrival
                            else None
                        )

                    # Create content state with all required fields
                    import time

                    content_state = {
                        "status": (
                            journey.snapshots[-1].train_status
                            if journey and journey.snapshots
                            else "UNKNOWN"
                        ),
                        "track": (
                            current_stop.track
                            if current_stop and current_stop.track
                            else None
                        ),
                        "currentStopName": (
                            current_stop.station_name if current_stop else "Unknown"
                        ),
                        "nextStopName": next_stop.station_name if next_stop else None,
                        "delayMinutes": calculated_delay,
                        "journeyProgress": journey_progress,
                        "dataTimestamp": int(
                            time.time()
                        ),  # Unix timestamp for data freshness
                        # New fields for enhanced Live Activity display
                        "scheduledDepartureTime": scheduled_departure_time,
                        "scheduledArrivalTime": scheduled_arrival_time,
                        "nextStopArrivalTime": next_stop_arrival_time,
                        "hasTrainDeparted": has_train_departed,
                        "originStationCode": token.origin_code,
                        "destinationStationCode": token.destination_code,
                    }

                    # Enhanced debug logging for Live Activity payload
                    logger.info(
                        "live_activity_content_state_detailed",
                        train_number=train_number,
                        # Progress tracking
                        journey_progress=journey_progress,
                        user_journey_stops=(
                            len(user_journey_stops)
                            if "user_journey_stops" in locals()
                            else "N/A"
                        ),
                        # Departure/arrival data
                        has_departed=has_train_departed,
                        scheduled_departure_time=scheduled_departure_time,
                        scheduled_arrival_time=scheduled_arrival_time,
                        next_stop_arrival_time=next_stop_arrival_time,
                        # Current state
                        current_stop=(
                            current_stop.station_name if current_stop else None
                        ),
                        current_stop_code=(
                            current_stop.station_code if current_stop else None
                        ),
                        next_stop=next_stop.station_name if next_stop else None,
                        next_stop_code=next_stop.station_code if next_stop else None,
                        # Track and status
                        track=content_state.get("track"),
                        status=content_state.get("status"),
                        delay_minutes=content_state.get("delayMinutes"),
                        # User journey
                        origin_code=token.origin_code,
                        destination_code=token.destination_code,
                        # Data validation
                        has_origin_stop=origin_stop is not None,
                        has_destination_stop=destination_stop is not None,
                        # Full payload for debugging
                        full_content_state=content_state,
                    )

                    # Send update to each token
                    for token in tokens:
                        try:
                            # Run async APNS call in sync context
                            success = await self.apns_service.send_live_activity_update(
                                token.push_token, content_state
                            )

                            # Mark token as inactive if it failed with 410
                            if not success:
                                token.is_active = False
                                session.commit()

                        except Exception as e:
                            logger.error(
                                "live_activity_update_failed",
                                train_number=train_number,
                                error=str(e),
                                error_type=type(e).__name__,
                            )

                logger.info(
                    "live_activity_updates_completed",
                    trains_updated=len(trains_to_update),
                )

            # Close sync engine when done
            sync_engine.dispose()

        except Exception as e:
            # Add more context for debugging
            import greenlet  # type: ignore[import-untyped]

            logger.error(
                "live_activity_update_error",
                error=str(e),
                error_type=type(e).__name__,
                has_running_loop=asyncio._get_running_loop() is not None,
                current_task_name=(
                    task.get_name()
                    if (task := asyncio.current_task()) is not None
                    else None
                ),
                greenlet_current=(
                    str(greenlet.getcurrent()) if greenlet else "no greenlet module"
                ),
            )
        finally:
            # Remove from running tasks
            self._running_tasks.pop(task_id, None)

    def _is_stale(self, last_updated: datetime, threshold_seconds: int = 60) -> bool:
        """Check if data is older than threshold.

        Args:
            last_updated: Last update timestamp
            threshold_seconds: Staleness threshold in seconds (default: 60)

        Returns:
            True if data is stale, False otherwise
        """
        return (
            safe_datetime_subtract(now_et(), last_updated).total_seconds()
            > threshold_seconds
        )

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status and job information."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "pending": job.pending,
                }
            )

        return {
            "running": self.scheduler.running,
            "jobs_count": len(jobs),
            "jobs": jobs,
            "active_tasks": list(self._running_tasks.keys()),
        }


# Global scheduler instance
_scheduler: SchedulerService | None = None


def get_scheduler(apns_service: SimpleAPNSService | None = None) -> SchedulerService:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService(apns_service=apns_service)
    return _scheduler
