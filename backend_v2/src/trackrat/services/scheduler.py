"""
In-process scheduler service for TrackRat V2.

Uses APScheduler to run periodic tasks within the FastAPI application.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.collectors.lirr.collector import LIRRCollector
from trackrat.collectors.mnr.collector import MNRCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.service_alerts import collect_service_alerts
from trackrat.collectors.subway.collector import SubwayCollector
from trackrat.collectors.wmata.collector import WMATACollector
from trackrat.db.engine import get_session
from trackrat.models.database import LiveActivityToken, TrainJourney
from trackrat.services.alert_evaluator import (
    evaluate_morning_digests,
    evaluate_route_alerts,
    evaluate_service_alerts,
)
from trackrat.services.amtrak_pattern_scheduler import AmtrakPatternScheduler
from trackrat.services.apns import SimpleAPNSService
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.settings import Settings, get_settings
from trackrat.utils.scheduler_utils import (
    calculate_safe_interval,
    commit_with_retry,
    run_with_freshness_check,
)
from trackrat.utils.time import (
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
        self._sync_engine: Any = None  # Lazily created sync engine for NJT
        self._njt_collection_semaphore = asyncio.Semaphore(
            10
        )  # Cap concurrent NJT collections

    def _get_sync_engine(self) -> Any:
        """Get or create a cached synchronous database engine."""
        if self._sync_engine is None:
            from sqlalchemy import create_engine

            db_url = str(self.settings.database_url).replace(
                "postgresql+asyncpg", "postgresql"
            )
            self._sync_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                connect_args={
                    "application_name": "trackrat-v2-sync",
                    "options": "-c statement_timeout=60000 -c jit=off -c timezone=America/New_York",
                },
            )
        return self._sync_engine

    @staticmethod
    def _log_task_exception(task: asyncio.Task[Any]) -> None:
        """Log unhandled exceptions from fire-and-forget tasks."""
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                "background_task_failed",
                task_name=task.get_name(),
                error=str(task.exception()),
                error_type=type(task.exception()).__name__,
            )

    async def start(self) -> None:
        """Start the scheduler and configure jobs."""
        logger.info("starting_scheduler_service")

        # Initialize NJ Transit client
        self.njt_client = NJTransitClient(self.settings)

        # Initialize JIT service with the NJ Transit client
        self.jit_service = JustInTimeUpdateService(self.njt_client)

        # Reference time for staggering interval triggers to prevent thundering herd
        now = now_et()

        # Schedule NJT discovery job
        self.scheduler.add_job(
            self.run_njt_discovery,
            trigger=IntervalTrigger(
                minutes=self.settings.discovery_interval_minutes, jitter=60
            ),
            id="njt_train_discovery",
            name="NJT Train Discovery",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            misfire_grace_time=300,  # 5 minute grace period
        )

        # Schedule Amtrak discovery job - staggered 5min from NJT
        self.scheduler.add_job(
            self.run_amtrak_discovery,
            trigger=IntervalTrigger(
                minutes=self.settings.discovery_interval_minutes,
                start_date=now + timedelta(minutes=5),
                jitter=60,
            ),
            id="amtrak_train_discovery",
            name="Amtrak Train Discovery",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )

        # Schedule 4-min collectors staggered 1 minute apart to prevent
        # all four from hitting CPU/network simultaneously
        self.scheduler.add_job(
            self.run_path_collection,
            trigger=IntervalTrigger(minutes=4, jitter=30),
            id="path_collection",
            name="PATH Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )

        self.scheduler.add_job(
            self.run_lirr_collection,
            trigger=IntervalTrigger(
                minutes=4, start_date=now + timedelta(minutes=1), jitter=30
            ),
            id="lirr_collection",
            name="LIRR Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )

        self.scheduler.add_job(
            self.run_mnr_collection,
            trigger=IntervalTrigger(
                minutes=4, start_date=now + timedelta(minutes=2), jitter=30
            ),
            id="mnr_collection",
            name="MNR Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )

        self.scheduler.add_job(
            self.run_wmata_collection,
            trigger=IntervalTrigger(minutes=3, jitter=30),
            id="wmata_collection",
            name="WMATA Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )

        self.scheduler.add_job(
            self.run_subway_collection,
            trigger=IntervalTrigger(
                minutes=4, start_date=now + timedelta(minutes=3), jitter=30
            ),
            id="subway_collection",
            name="Subway Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )

        # Schedule journey collection check (every 5 minutes)
        # This checks for trains needing updates and schedules them
        self.scheduler.add_job(
            self.check_journey_updates,
            trigger=IntervalTrigger(minutes=5, jitter=30),
            id="journey_update_check",
            name="Journey Update Check",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule Live Activity updates (every minute)
        self.scheduler.add_job(
            self.update_live_activities,
            trigger=IntervalTrigger(minutes=1, jitter=10),
            id="live_activity_updates",
            name="Live Activity Updates",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule Live Activity token cleanup (every hour)
        self.scheduler.add_job(
            self.cleanup_expired_live_activity_tokens,
            trigger=IntervalTrigger(hours=1, jitter=120),
            id="live_activity_token_cleanup",
            name="Live Activity Token Cleanup",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule congestion API cache pre-computation (every 15 minutes)
        self.scheduler.add_job(
            self.precompute_congestion_cache,
            trigger=IntervalTrigger(minutes=15, jitter=60),
            id="congestion_cache_precompute",
            name="Congestion Cache Pre-computation",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule departures API cache pre-computation (every 90 seconds)
        self.scheduler.add_job(
            self.precompute_departure_cache,
            trigger=IntervalTrigger(seconds=90, jitter=15),
            id="departure_cache_precompute",
            name="Departure Cache Pre-computation",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # Schedule route history API cache pre-computation (every 5 minutes)
        self.scheduler.add_job(
            self.precompute_route_history_cache,
            trigger=IntervalTrigger(minutes=5, jitter=30),
            id="route_history_cache_precompute",
            name="Route History Cache Pre-computation",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # Schedule train validation (every hour, offset 10min from token cleanup)
        self.scheduler.add_job(
            self.run_train_validation,
            trigger=IntervalTrigger(
                hours=1, start_date=now + timedelta(minutes=10), jitter=120
            ),
            id="train_validation",
            name="End-to-End Train Validation",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )

        # Schedule NJT schedule collection (daily at 12:30 AM)
        self.scheduler.add_job(
            self.collect_njt_schedules,
            trigger=CronTrigger(hour=0, minute=30, timezone="America/New_York"),
            id="njt_schedule_collection",
            name="NJT Daily Schedule Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=900,  # 15 minute grace period
        )

        # Schedule Amtrak pattern-based schedule generation (daily at 12:45 AM)
        self.scheduler.add_job(
            self.generate_amtrak_schedules,
            trigger=CronTrigger(hour=0, minute=45, timezone="America/New_York"),
            id="amtrak_schedule_generation",
            name="Amtrak Pattern Schedule Generation",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=900,  # 15 minute grace period
        )

        # Schedule lock manager cleanup (daily at 1:00 AM)
        self.scheduler.add_job(
            self.cleanup_old_locks,
            trigger=CronTrigger(hour=1, minute=0, timezone="America/New_York"),
            id="lock_manager_cleanup",
            name="Lock Manager Cleanup",
            replace_existing=True,
            max_instances=1,
        )

        # Schedule GTFS static schedule refresh (daily at 3:00 AM)
        # This downloads and parses GTFS feeds for future date schedules
        self.scheduler.add_job(
            self.refresh_gtfs_feeds,
            trigger=CronTrigger(hour=3, minute=0, timezone="America/New_York"),
            id="gtfs_feed_refresh",
            name="GTFS Static Schedule Refresh",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,  # 1 hour grace period
        )

        # Schedule route alert evaluation (every 5 minutes, offset from journey check)
        self.scheduler.add_job(
            self.run_alert_evaluation,
            trigger=IntervalTrigger(
                minutes=5, start_date=now + timedelta(minutes=2), jitter=30
            ),
            id="route_alert_evaluation",
            name="Route Alert Evaluation",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,  # 5 minute grace period (matches interval)
        )

        # Schedule morning digest evaluation (every 5 minutes, offset from alert eval)
        self.scheduler.add_job(
            self.run_morning_digest_evaluation,
            trigger=IntervalTrigger(
                minutes=5, start_date=now + timedelta(minutes=3), jitter=30
            ),
            id="morning_digest_evaluation",
            name="Morning Digest Evaluation",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )

        # Schedule service alerts collection (every 15 minutes) - MTA + NJT
        self.scheduler.add_job(
            self.run_service_alerts_collection,
            trigger=IntervalTrigger(
                minutes=15, start_date=now + timedelta(minutes=4), jitter=60
            ),
            id="service_alerts_collection",
            name="Service Alerts Collection (MTA + NJT)",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=900,  # 15 minute grace period
        )

        # Start the scheduler
        self.scheduler.start()

        # Run initial collections staggered to avoid startup CPU spike
        asyncio.create_task(self._run_startup_collectors()).add_done_callback(
            self._log_task_exception
        )

        # Check and initialize GTFS feeds on startup (downloads if missing)
        asyncio.create_task(self.check_and_initialize_gtfs_feeds()).add_done_callback(
            self._log_task_exception
        )

        logger.info(
            "scheduler_started", jobs=[job.id for job in self.scheduler.get_jobs()]
        )

    async def _run_startup_collectors(self) -> None:
        """Launch startup collectors with staggered delays to avoid CPU spike."""
        collectors = [
            ("njt_discovery", self.run_njt_discovery),
            ("amtrak_discovery", self.run_amtrak_discovery),
            ("path_collection", self.run_path_collection),
            ("lirr_collection", self.run_lirr_collection),
            ("mnr_collection", self.run_mnr_collection),
            ("subway_collection", self.run_subway_collection),
            ("wmata_collection", self.run_wmata_collection),
        ]
        for name, collector in collectors:
            logger.info("startup_collector_launch", collector=name)
            asyncio.create_task(collector())
            await asyncio.sleep(10)

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

        # Dispose cached sync engine
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None

        logger.info("scheduler_stopped")

    async def run_njt_discovery(self) -> None:
        """Run NJ Transit train discovery for all configured stations."""
        task_id = f"njt_discovery_{now_et().isoformat()}"

        async def do_discovery_work() -> None:
            """The actual discovery work, wrapped for freshness checking."""
            try:
                logger.info(
                    "starting_train_discovery_task",
                    task="njt_discovery",
                    scheduled_interval_minutes=self.settings.discovery_interval_minutes,
                )

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
                    task="njt_discovery",
                    total_discovered=result.get("total_discovered", 0),
                    total_new=result.get("total_new", 0),
                    safe_interval_seconds=calculate_safe_interval(
                        self.settings.discovery_interval_minutes
                    ),
                )

                # Schedule batch collection for ALL discovered trains
                # This ensures all trains have their journey details collected
                if result.get("total_discovered", 0) > 0:
                    await self.schedule_njt_batch_collection(result)

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        async with get_session() as db:
            # Calculate safe interval based on configured discovery interval
            safe_interval = calculate_safe_interval(
                self.settings.discovery_interval_minutes
            )

            executed = await run_with_freshness_check(
                db=db,
                task_name="njt_discovery",
                minimum_interval_seconds=safe_interval,
                task_func=do_discovery_work,
            )

            if not executed:
                logger.debug("njt_discovery_skipped_still_fresh")

    async def run_amtrak_discovery(self) -> None:
        """Run Amtrak train discovery for trains serving NYP."""
        task_id = f"amtrak_discovery_{now_et().isoformat()}"

        async def do_amtrak_discovery_work() -> None:
            """The actual Amtrak discovery work, wrapped for freshness checking."""
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

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        async with get_session() as db:
            # Calculate safe interval based on configured discovery interval
            safe_interval = calculate_safe_interval(
                self.settings.discovery_interval_minutes
            )

            executed = await run_with_freshness_check(
                db=db,
                task_name="amtrak_discovery",
                minimum_interval_seconds=safe_interval,
                task_func=do_amtrak_discovery_work,
            )

            if not executed:
                logger.debug("amtrak_discovery_skipped_still_fresh")

    async def run_path_collection(self) -> None:
        """Run unified PATH collection (discovery + journey updates)."""
        task_id = f"path_collection_{now_et().isoformat()}"

        async def do_path_collection_work() -> dict[str, Any]:
            """The actual PATH collection work, wrapped for freshness checking."""
            try:
                logger.info("starting_path_collection")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Run unified PATH collection
                collector = PathCollector()
                result = await collector.run()

                logger.info(
                    "path_collection_completed",
                    arrivals_fetched=result.get("arrivals_fetched", 0),
                    new_journeys=result.get("new_journeys", 0),
                    updated=result.get("updated", 0),
                    completed=result.get("completed", 0),
                )
                return result

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        async with get_session() as db:
            # 4 minute interval, use 90% = 216 seconds safe interval
            safe_interval = calculate_safe_interval(4)

            executed = await run_with_freshness_check(
                db=db,
                task_name="path_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_path_collection_work,
            )

            if not executed:
                logger.debug("path_collection_skipped_still_fresh")

    async def run_lirr_collection(self) -> None:
        """Run unified LIRR collection (discovery + journey updates)."""
        task_id = f"lirr_collection_{now_et().isoformat()}"

        async def do_lirr_collection_work() -> dict[str, Any]:
            """The actual LIRR collection work, wrapped for freshness checking."""
            try:
                logger.info("starting_lirr_collection")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Run unified LIRR collection
                collector = LIRRCollector()
                try:
                    result = await collector.run()

                    logger.info(
                        "lirr_collection_completed",
                        total_arrivals=result.get("total_arrivals", 0),
                        discovered=result.get("discovered", 0),
                        updated=result.get("updated", 0),
                        errors=result.get("errors", 0),
                    )
                    return result
                finally:
                    await collector.close()

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        async with get_session() as db:
            # 4 minute interval, use 90% = 216 seconds safe interval
            safe_interval = calculate_safe_interval(4)

            executed = await run_with_freshness_check(
                db=db,
                task_name="lirr_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_lirr_collection_work,
            )

            if not executed:
                logger.debug("lirr_collection_skipped_still_fresh")

    async def run_mnr_collection(self) -> None:
        """Run unified Metro-North collection (discovery + journey updates)."""
        task_id = f"mnr_collection_{now_et().isoformat()}"

        async def do_mnr_collection_work() -> dict[str, Any]:
            """The actual MNR collection work, wrapped for freshness checking."""
            try:
                logger.info("starting_mnr_collection")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Run unified MNR collection
                collector = MNRCollector()
                try:
                    result = await collector.run()

                    logger.info(
                        "mnr_collection_completed",
                        total_arrivals=result.get("total_arrivals", 0),
                        discovered=result.get("discovered", 0),
                        updated=result.get("updated", 0),
                        errors=result.get("errors", 0),
                    )
                    return result
                finally:
                    await collector.close()

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        async with get_session() as db:
            # 4 minute interval, use 90% = 216 seconds safe interval
            safe_interval = calculate_safe_interval(4)

            executed = await run_with_freshness_check(
                db=db,
                task_name="mnr_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_mnr_collection_work,
            )

            if not executed:
                logger.debug("mnr_collection_skipped_still_fresh")

    async def run_subway_collection(self) -> None:
        """Run unified NYC Subway collection (discovery + journey updates)."""
        task_id = f"subway_collection_{now_et().isoformat()}"

        async def do_subway_collection_work() -> dict[str, Any]:
            """The actual Subway collection work, wrapped for freshness checking."""
            try:
                logger.info("starting_subway_collection")

                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                collector = SubwayCollector()
                try:
                    result = await collector.run()

                    logger.info(
                        "subway_collection_completed",
                        total_arrivals=result.get("total_arrivals", 0),
                        discovered=result.get("discovered", 0),
                        updated=result.get("updated", 0),
                        errors=result.get("errors", 0),
                    )
                    return result
                finally:
                    await collector.close()

            finally:
                self._running_tasks.pop(task_id, None)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(4)

            executed = await run_with_freshness_check(
                db=db,
                task_name="subway_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_subway_collection_work,
            )

            if not executed:
                logger.debug("subway_collection_skipped_still_fresh")

    async def run_wmata_collection(self) -> None:
        """Run unified WMATA collection (discovery + journey updates)."""
        task_id = f"wmata_collection_{now_et().isoformat()}"

        async def do_wmata_collection_work() -> dict[str, Any]:
            """The actual WMATA collection work, wrapped for freshness checking."""
            try:
                logger.info("starting_wmata_collection")

                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                collector = WMATACollector()
                try:
                    result = await collector.run()

                    logger.info(
                        "wmata_collection_completed",
                        arrivals_fetched=result.get("arrivals_fetched", 0),
                        new_journeys=result.get("new_journeys", 0),
                        updated=result.get("updated", 0),
                        completed=result.get("completed", 0),
                    )
                    return result
                finally:
                    if collector.client:
                        await collector.client.close()

            finally:
                self._running_tasks.pop(task_id, None)

        async with get_session() as db:
            # 3 minute interval, use 90% = 162 seconds safe interval
            safe_interval = calculate_safe_interval(3)

            executed = await run_with_freshness_check(
                db=db,
                task_name="wmata_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_wmata_collection_work,
            )

            if not executed:
                logger.debug("wmata_collection_skipped_still_fresh")

    async def check_journey_updates(self) -> None:
        """Check for trains needing journey updates."""
        task_id = f"journey_check_{now_et().isoformat()}"

        async def do_journey_check_work() -> None:
            """The actual journey check work, wrapped for freshness checking."""
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

            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        # This runs every 5 minutes, so use a 4-minute minimum interval
        async with get_session() as db:
            safe_interval = calculate_safe_interval(5)  # 5-minute scheduled interval

            executed = await run_with_freshness_check(
                db=db,
                task_name="journey_update_check",
                minimum_interval_seconds=safe_interval,
                task_func=do_journey_check_work,
            )

            if not executed:
                logger.debug("journey_update_check_skipped_still_fresh")

    async def schedule_departure_collections(self, session: AsyncSession) -> None:
        """Schedule collection for trains at their departure time and hot train updates.

        This function handles two types of updates:
        1. Departure-time collection: For trains without complete journey data,
           schedule collection at their departure time.
        2. Hot train updates: For trains departing within the hot window (default 15 min)
           that have stale data (default >120s old), schedule immediate updates.
           This ensures track assignments, delays, and status changes are captured
           more frequently near departure time.
        """
        window_start = now_et()
        hot_window_end = window_start + timedelta(
            minutes=self.settings.hot_train_window_minutes
        )
        hot_staleness_cutoff = window_start - timedelta(
            seconds=self.settings.hot_train_update_interval_seconds
        )

        # Query 1: Trains without complete journey data (schedule at departure time)
        # Use 10-minute window for departure-time collection (original behavior)
        departure_window_end = window_start + timedelta(minutes=10)
        stmt_incomplete = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.has_complete_journey.is_not(True),
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.scheduled_departure >= window_start,
                    TrainJourney.scheduled_departure <= departure_window_end,
                )
            )
            .limit(100)
        )

        result_incomplete = await session.execute(stmt_incomplete)
        incomplete_trains = list(result_incomplete.scalars().all())

        # Query 2: Hot trains with complete journey but stale data (schedule immediately)
        stmt_hot = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.has_complete_journey.is_(True),
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_expired.is_not(True),
                    TrainJourney.scheduled_departure >= window_start,
                    TrainJourney.scheduled_departure <= hot_window_end,
                    TrainJourney.last_updated_at < hot_staleness_cutoff,
                )
            )
            .limit(100)
        )

        result_hot = await session.execute(stmt_hot)
        hot_trains = list(result_hot.scalars().all())

        departure_scheduled_count = 0
        hot_update_count = 0

        # Schedule departure-time collection for incomplete trains
        for train in incomplete_trains:
            job_id = f"departure_collection_{train.train_id}_{train.journey_date}"

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
                departure_scheduled_count += 1

        # Schedule immediate updates for hot trains with stale data
        for train in hot_trains:
            job_id = f"hot_update_{train.train_id}_{train.journey_date}"

            if not self.scheduler.get_job(job_id):
                self.scheduler.add_job(
                    self.collect_journey,
                    trigger=DateTrigger(run_date=now_et()),
                    args=[train.train_id, train.journey_date],
                    id=job_id,
                    name=f"Hot update for {train.train_id}",
                    replace_existing=True,
                    max_instances=1,
                )
                hot_update_count += 1

        # Log batch summaries
        if departure_scheduled_count > 0:
            logger.info(
                "scheduler.departure.scheduled",
                count=departure_scheduled_count,
                window_minutes=10,
            )

        if hot_update_count > 0:
            logger.info(
                "scheduler.hot_train.scheduled",
                count=hot_update_count,
                window_minutes=self.settings.hot_train_window_minutes,
                staleness_seconds=self.settings.hot_train_update_interval_seconds,
            )

    async def schedule_periodic_updates(self, session: AsyncSession) -> None:
        """Schedule periodic updates for active trains."""
        # Find trains that need periodic updates
        current_time = now_et()
        cutoff_time = current_time - timedelta(
            minutes=self.settings.journey_update_interval_minutes
        )

        # Get candidates without timezone-sensitive comparisons
        # Only consider today and yesterday (for midnight-crossing trains)
        min_journey_date = current_time.date() - timedelta(days=1)
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.has_complete_journey.is_(True),
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_expired.is_not(True),  # Exclude expired trains
                    TrainJourney.journey_date >= min_journey_date,
                )
            )
            .limit(50)
        )  # Get more candidates since we'll filter in Python

        result = await session.execute(stmt)
        all_trains = result.scalars().all()

        # Filter with proper timezone handling
        trains = []
        for train in all_trains:
            if train.last_updated_at:
                last_updated = ensure_timezone_aware(train.last_updated_at)
                if last_updated < cutoff_time:
                    trains.append(train)

        scheduled_count = 0
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
                scheduled_count += 1

        # Log batch summary instead of individual trains
        if scheduled_count > 0:
            logger.info(
                "scheduler.periodic.scheduled",
                count=scheduled_count,
                total_active_trains=len(trains),
            )

    async def collect_journey(self, train_id: str, journey_date: datetime) -> None:
        """Collect journey data for a specific train."""
        task_id = f"journey_{train_id}_{now_et().isoformat()}"

        try:
            # Debug level for individual collection start
            logger.debug(
                "journey.collection.started",
                train_id=train_id,
                journey_date=journey_date,
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

            # Use the safe collection method that handles greenlet issues
            # This wraps the collection in a new async task to ensure proper context
            j_date = (
                journey_date.date()
                if isinstance(journey_date, datetime)
                else journey_date
            )
            result = await asyncio.create_task(
                self._collect_single_njt_journey_safe(train_id, j_date)
            )

            if result:
                # Debug level for successful collection
                logger.debug(
                    "journey.collection.completed",
                    train_id=train_id,
                    is_completed=result.get("is_completed", False),
                    stops_count=result.get("stops_count", 0),
                )
            else:
                # Error for actual failures
                logger.error(
                    "journey.collection.failed",
                    train_id=train_id,
                    error="No result returned from collection",
                )

        except Exception as e:
            logger.error(
                "journey.collection.error",
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
                    # Look for journeys from today or tomorrow to handle midnight edge case
                    current_date = now_et().date()
                    stmt = select(TrainJourney).where(
                        and_(
                            TrainJourney.train_id == train_id,
                            TrainJourney.journey_date.in_(
                                [current_date, current_date + timedelta(days=1)]
                            ),
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
                    # Skip expired, completed, or cancelled trains
                    if (
                        journey.is_expired
                        or journey.is_completed
                        or journey.is_cancelled
                    ):
                        continue

                    # Collect if no complete journey data or data is stale (>15 minutes)
                    needs_collection = (
                        not journey.has_complete_journey
                        or journey.last_updated_at is None
                        or safe_datetime_subtract(
                            now_et(), ensure_timezone_aware(journey.last_updated_at)
                        ).total_seconds()
                        > 900
                    )

                    if needs_collection:
                        trains_to_collect.append(train_id)
                    else:
                        logger.debug(
                            "njt_journey_recently_updated",
                            train_id=train_id,
                            last_updated=(
                                ensure_timezone_aware(
                                    journey.last_updated_at
                                ).isoformat()
                                if journey.last_updated_at
                                else None
                            ),
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
            args=[trains_to_collect, current_date],
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

        # Filter out trains that already have OBSERVED journeys.
        # SCHEDULED trains still need collection to promote them to OBSERVED.
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
                elif existing_journey.observation_type == "SCHEDULED":
                    # SCHEDULED trains need collection to promote to OBSERVED
                    trains_to_collect.append(original_train_id)
                    logger.debug(
                        "amtrak_scheduled_needs_promotion",
                        train_id=original_train_id,
                        internal_id=internal_train_id,
                    )
                else:
                    logger.debug(
                        "amtrak_journey_already_observed",
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

            # Process trains sequentially for consistent performance
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

    def _determine_train_status_sync(self, stops_data: list[Any]) -> str:
        """Determine overall train status from stops (sync version).

        Args:
            stops_data: List of NJTransitStopData

        Returns:
            Overall status string
        """
        if not stops_data:
            return "UNKNOWN"

        # Check if all stops are cancelled
        if all((stop.STOP_STATUS or "") == "CANCELLED" for stop in stops_data):
            return "CANCELLED"

        # Find current position
        for i, stop in enumerate(stops_data):
            if stop.DEPARTED != "YES":
                # This is the next stop
                if i == 0:
                    return "NOT_DEPARTED"
                elif stop.TRACK:
                    return "BOARDING"
                else:
                    return "IN_TRANSIT"

        # All stops departed
        return "COMPLETED"

    async def _collect_single_njt_journey_safe(
        self, train_id: str, journey_date: date | None = None
    ) -> dict[str, Any] | None:
        """Safely collect a single NJT journey using synchronous database operations.

        This method splits DB access into read and write phases around the external
        NJT API call, so that no database connection is held while waiting for the
        network response.  This prevents connection pool exhaustion when many trains
        are collected concurrently.

        Args:
            train_id: The train ID to collect
            journey_date: The journey date to filter by (defaults to today if not provided)

        Returns:
            Dict with journey info if successful, None if failed
        """
        try:
            from sqlalchemy import and_, delete, select
            from sqlalchemy.orm import sessionmaker

            from trackrat.collectors.njt.client import (
                NJTransitNullDataError,
                TrainNotFoundError,
            )
            from trackrat.models.database import JourneySnapshot, JourneyStop
            from trackrat.utils.time import now_et, parse_njt_time

            if journey_date is None:
                journey_date = now_et().date()

            SyncSession = sessionmaker(self._get_sync_engine())
            with SyncSession() as session:
                stmt = select(
                    TrainJourney.id,
                    TrainJourney.is_expired,
                    TrainJourney.api_error_count,
                ).where(
                    and_(
                        TrainJourney.train_id == train_id,
                        TrainJourney.journey_date == journey_date,
                        TrainJourney.data_source == "NJT",
                    )
                )
                row = session.execute(stmt).first()

            # Connection returned to pool here

            if not row:
                logger.warning("journey_not_found_sync", train_id=train_id)
                return None

            journey_id = row.id
            journey_is_expired = row.is_expired
            journey_api_error_count = row.api_error_count or 0

            if journey_is_expired:
                logger.debug("skipping_expired_train_sync", train_id=train_id)
                return None

            # ── Phase 2: Call NJT API (no DB connection held) ──
            # Semaphore caps concurrent API calls to prevent overwhelming
            # the NJT API and downstream DB write contention.
            if not self.njt_client:
                logger.error("njt_client_not_initialized", train_id=train_id)
                return None

            try:
                async with self._njt_collection_semaphore:
                    train_data = await self.njt_client.get_train_stop_list(train_id)
            except NJTransitNullDataError:
                logger.info(
                    "train_null_data_skipped_sync",
                    train_id=train_id,
                    journey_id=journey_id,
                    api_error_count=journey_api_error_count,
                )
                return {
                    "train_id": train_id,
                    "success": False,
                    "error": "Transient null data",
                    "expired": False,
                }
            except TrainNotFoundError:
                # Train is genuinely not available — increment error count.
                new_error_count = journey_api_error_count + 1
                is_now_expired = new_error_count >= 3

                with SyncSession() as session:
                    journey = session.get(TrainJourney, journey_id)
                    if journey:
                        journey.api_error_count = new_error_count
                        journey.last_updated_at = now_et()
                        journey.update_count = (journey.update_count or 0) + 1
                        if is_now_expired:
                            journey.is_expired = True
                            logger.warning(
                                "train_marked_expired_sync",
                                train_id=train_id,
                                journey_id=journey_id,
                                error_count=new_error_count,
                            )
                        commit_with_retry(session, log_context={"train_id": train_id})

                return {
                    "train_id": train_id,
                    "success": False,
                    "error": "Train not found",
                    "expired": is_now_expired,
                }

            if not train_data:
                logger.warning("no_train_data_received_sync", train_id=train_id)
                return None

            # ── Phase 3: Write results to DB (connection held only for writes) ──
            with SyncSession() as session:
                journey = session.get(TrainJourney, journey_id)
                if not journey:
                    logger.warning(
                        "journey_disappeared_before_write",
                        train_id=train_id,
                        journey_id=journey_id,
                    )
                    return None

                # Reset error count on successful fetch
                journey.api_error_count = 0

                with session.no_autoflush:
                    # Update journey metadata
                    journey.destination = train_data.DESTINATION
                    journey.line_color = train_data.BACKCOLOR.strip()
                    journey.has_complete_journey = True
                    journey.stops_count = len(train_data.STOPS)
                    journey.last_updated_at = now_et()
                    journey.update_count = (journey.update_count or 0) + 1

                    # Update origin/terminal/scheduled_departure from stops
                    if train_data.STOPS:
                        first_stop = train_data.STOPS[0]
                        last_stop = train_data.STOPS[-1]

                        journey.origin_station_code = first_stop.STATION_2CHAR
                        journey.terminal_station_code = last_stop.STATION_2CHAR
                        if first_stop.DEP_TIME:
                            journey.scheduled_departure = parse_njt_time(
                                first_stop.DEP_TIME
                            )
                        if last_stop.TIME:
                            journey.scheduled_arrival = parse_njt_time(last_stop.TIME)

                    # Delete existing stops
                    session.execute(
                        delete(JourneyStop).where(JourneyStop.journey_id == journey.id)
                    )

                    # Create new stops
                    for idx, stop_data in enumerate(train_data.STOPS):
                        scheduled_arrival = (
                            parse_njt_time(stop_data.TIME) if stop_data.TIME else None
                        )
                        scheduled_departure = (
                            parse_njt_time(stop_data.DEP_TIME)
                            if stop_data.DEP_TIME
                            else None
                        )

                        is_stop_cancelled = (stop_data.STOP_STATUS or "") == "CANCELLED"
                        actual_arrival = None
                        actual_departure = None
                        if stop_data.DEPARTED == "YES" and not is_stop_cancelled:
                            actual_arrival = scheduled_arrival
                            actual_departure = scheduled_departure

                        stop = JourneyStop(
                            journey_id=journey.id,
                            station_code=stop_data.STATION_2CHAR,
                            station_name=stop_data.STATIONNAME,
                            stop_sequence=idx,
                            scheduled_departure=scheduled_departure,
                            scheduled_arrival=scheduled_arrival,
                            actual_departure=actual_departure,
                            actual_arrival=actual_arrival,
                            track=stop_data.TRACK or None,
                            track_assigned_at=now_et() if stop_data.TRACK else None,
                            raw_njt_departed_flag=stop_data.DEPARTED,
                            has_departed_station=(
                                stop_data.DEPARTED == "YES"
                                and not is_stop_cancelled
                                and (
                                    not scheduled_departure
                                    or scheduled_departure <= now_et()
                                )
                            ),
                        )
                        session.add(stop)

                    # Create/update journey snapshot
                    session.execute(
                        delete(JourneySnapshot).where(
                            JourneySnapshot.journey_id == journey.id
                        )
                    )

                    completed_stops = sum(
                        1
                        for stop in train_data.STOPS
                        if stop.DEPARTED == "YES"
                        and (stop.STOP_STATUS or "") != "CANCELLED"
                    )

                    track_assignments = {
                        stop.STATION_2CHAR: stop.TRACK
                        for stop in train_data.STOPS
                        if stop.TRACK
                    }

                    delay_minutes = 0
                    for stop in reversed(train_data.STOPS):
                        if stop.DEPARTED == "YES" and stop.STOP_STATUS:
                            if "LATE" in (stop.STOP_STATUS or ""):
                                try:
                                    parts = stop.STOP_STATUS.split()
                                    if "MINUTES" in parts:
                                        idx = parts.index("MINUTES")
                                        if idx > 0:
                                            delay_minutes = int(parts[idx - 1])
                                    elif "MINS" in parts:
                                        idx = parts.index("MINS")
                                        if idx > 0:
                                            delay_minutes = int(parts[idx - 1])
                                except (ValueError, IndexError):
                                    pass
                            break

                    train_status = self._determine_train_status_sync(train_data.STOPS)

                    snapshot = JourneySnapshot(
                        journey_id=journey.id,
                        captured_at=now_et(),
                        raw_stop_list_data={},
                        train_status=train_status,
                        delay_minutes=delay_minutes,
                        completed_stops=completed_stops,
                        total_stops=len(train_data.STOPS),
                        track_assignments=track_assignments,
                    )
                    session.add(snapshot)

                    # Update journey status from stops
                    is_completed = bool(
                        train_data.STOPS and train_data.STOPS[-1].DEPARTED == "YES"
                    )
                    journey.is_completed = is_completed

                    is_cancelled = all(
                        (stop.STOP_STATUS or "") == "CANCELLED"
                        for stop in train_data.STOPS
                    )
                    if is_cancelled:
                        journey.is_cancelled = True
                        journey.cancellation_reason = "All stops cancelled by NJT"

                result_data = {
                    "train_id": train_id,
                    "stops_count": len(train_data.STOPS),
                    "destination": train_data.DESTINATION,
                    "success": True,
                    "is_completed": is_completed,
                }

                commit_with_retry(session, log_context={"train_id": train_id})

            logger.info(
                "journey_collection_completed_sync",
                train_id=train_id,
                journey_id=journey_id,
                stops_count=len(train_data.STOPS),
                is_completed=is_completed,
            )

            return result_data

        except Exception as e:
            error_msg = str(e).lower()
            is_transient = (
                "serialization failure" in error_msg
                or "deadlock detected" in error_msg
                or "could not serialize access" in error_msg
            )
            if is_transient:
                logger.warning(
                    "safe_journey_collection_transient_error",
                    train_id=train_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return {
                    "train_id": train_id,
                    "success": False,
                    "error": "Transient DB error",
                    "retry_needed": True,
                }
            else:
                logger.error(
                    "safe_journey_collection_failed",
                    train_id=train_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return None

    async def collect_njt_journeys_batch(
        self, train_ids: list[str], journey_date: date | None = None
    ) -> None:
        """Collect journey data for multiple NJ Transit trains in batch.

        Args:
            train_ids: List of NJ Transit train IDs to collect
            journey_date: The journey date for these trains (defaults to today)
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

            # Use synchronous processing to avoid greenlet issues with APScheduler
            # This is similar to the approach used in update_live_activities
            success_count = 0
            error_count = 0

            for i, train_id in enumerate(train_ids):
                try:
                    logger.debug(
                        "collecting_njt_journey",
                        train_id=train_id,
                        progress=f"{i+1}/{len(train_ids)}",
                    )

                    # Process each train in a fresh async context to avoid greenlet issues
                    # This creates a new task for each collection to ensure proper context
                    result = await asyncio.create_task(
                        self._collect_single_njt_journey_safe(train_id, journey_date)
                    )

                    if result:
                        if result.get("retry_needed"):
                            # Database was locked, wait and retry
                            logger.info(
                                "retrying_njt_journey_collection",
                                train_id=train_id,
                                reason="Database locked",
                            )
                            await asyncio.sleep(1.0)  # Wait a bit before retry
                            retry_result = await asyncio.create_task(
                                self._collect_single_njt_journey_safe(
                                    train_id, journey_date
                                )
                            )
                            if retry_result and retry_result.get("success"):
                                success_count += 1
                                logger.debug(
                                    "njt_journey_collected_on_retry",
                                    train_id=train_id,
                                    stops_count=retry_result.get("stops_count", 0),
                                )
                            else:
                                error_count += 1
                                logger.warning(
                                    "njt_journey_retry_failed",
                                    train_id=train_id,
                                )
                        elif result.get("success"):
                            success_count += 1
                            logger.debug(
                                "njt_journey_collected",
                                train_id=train_id,
                                stops_count=result.get("stops_count", 0),
                            )
                        else:
                            error_count += 1
                            logger.warning(
                                "njt_journey_collection_error",
                                train_id=train_id,
                                error=result.get("error", "Unknown error"),
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

    def _calculate_live_activity_content_state(
        self,
        journey: TrainJourney,
        token: LiveActivityToken,
        session: AsyncSession | Any,
    ) -> dict[str, Any]:
        """Calculate Live Activity content state for a specific token's journey segment."""
        import time

        from trackrat.utils.time import calculate_delay, ensure_timezone_aware, now_et

        # Calculate simple progress
        current_stop = None
        next_stop = None
        journey_progress = 0.0
        calculated_delay = 0  # Default delay

        if journey and journey.stops:
            # Sort stops by sequence to ensure proper ordering
            sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

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
                user_journey_stops = sorted_stops[origin_index : destination_index + 1]

                # Enhanced logging for debugging progress calculation differences
                stop_sequence_info = [
                    {
                        "sequence": s.stop_sequence,
                        "code": s.station_code,
                        "name": s.station_name,
                        "departed": s.has_departed_station,
                    }
                    for s in user_journey_stops
                ]

                logger.info(
                    "backend_progress_calculation_debug",
                    train_number=journey.train_id,
                    origin_code=token.origin_code,
                    destination_code=token.destination_code,
                    user_journey_stop_count=len(user_journey_stops),
                    total_stop_count=len(sorted_stops),
                    journey_stops=stop_sequence_info,
                )

                # Calculate progress based on user's journey only (includes destination in denominator)
                total_user_stops = len(user_journey_stops)
                departed_user_stops = sum(
                    1 for stop in user_journey_stops if stop.has_departed_station
                )
                journey_progress = (
                    departed_user_stops / total_user_stops
                    if total_user_stops > 0
                    else 0.0
                )

                logger.info(
                    "backend_progress_calculation_result",
                    train_number=journey.train_id,
                    total_stops=total_user_stops,
                    departed_stops=departed_user_stops,
                    progress=journey_progress,
                    calculation_method="departed_stops / total_stops (includes destination)",
                    note="iOS calculates progress as: departed_stops / (total_stops - 1) excluding destination",
                )

                # Find current and next stops within user's journey
                origin_station = user_journey_stops[0]
                has_departed_origin = origin_station.has_departed_station

                if not has_departed_origin:
                    # Train hasn't left origin yet - determine actual current position
                    # Don't assume train is at origin just because it hasn't departed
                    actual_current_stop = None
                    for stop in sorted_stops:
                        if (
                            journey.data_source == "AMTRAK"
                            and stop.raw_amtrak_status == "Station"
                        ) or (
                            journey.data_source == "NJT"
                            and stop.track
                            and not stop.has_departed_station
                        ):
                            actual_current_stop = stop
                            break

                    # If train is actually at the user's origin, show that
                    if (
                        actual_current_stop
                        and actual_current_stop.station_code == token.origin_code
                    ):
                        current_stop = actual_current_stop
                        next_stop = actual_current_stop
                    else:
                        # Train hasn't reached user's origin yet - show actual location or none
                        current_stop = actual_current_stop
                        next_stop = origin_station
                    logger.debug(
                        "user_journey_before_origin",
                        train_number=journey.train_id,
                        actual_current_stop=(
                            current_stop.station_name if current_stop else "Unknown"
                        ),
                        next_stop_name=(
                            next_stop.station_name if next_stop else "Unknown"
                        ),
                        user_journey_stops=total_user_stops,
                        train_at_origin=actual_current_stop
                        and actual_current_stop.station_code == token.origin_code,
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
                                train_number=journey.train_id,
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
                    train_number=journey.train_id,
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
                else sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
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
                dep_time = stop.updated_departure or stop.scheduled_departure
                scheduled_departure_time = dep_time.isoformat() if dep_time else None
                # Check if departed

                # Use has_departed_station as authoritative source
                if stop.has_departed_station:
                    has_train_departed = True
                elif stop.scheduled_departure:
                    # Use ensure_timezone_aware to properly handle timezone conversion
                    scheduled_dep = ensure_timezone_aware(stop.scheduled_departure)
                    current_time = now_et()
                    if scheduled_dep < current_time:
                        has_train_departed = True
            if stop.station_code == token.destination_code:
                destination_stop = stop
                # Convert to ISO8601 string for iOS
                arr_time = stop.updated_arrival or stop.scheduled_arrival
                scheduled_arrival_time = arr_time.isoformat() if arr_time else None

        # Get next stop arrival time
        if next_stop:
            # Convert to ISO8601 string for iOS
            next_arr_time = next_stop.updated_arrival or next_stop.scheduled_arrival
            next_stop_arrival_time = (
                next_arr_time.isoformat() if next_arr_time else None
            )

        # Determine status based on user's journey context
        if not has_train_departed:
            # Train hasn't left user's origin yet
            if current_stop and current_stop.station_code == token.origin_code:
                # Train is at user's origin
                if current_stop.track:
                    journey_status = "BOARDING"
                else:
                    journey_status = "ARRIVED_AT_ORIGIN"
            else:
                # Train hasn't reached user's origin yet
                journey_status = "NOT_DEPARTED"
        else:
            # Train has departed user's origin
            journey_status = (
                journey.snapshots[-1].train_status
                if journey and journey.snapshots and journey.snapshots[-1].train_status
                else "EN ROUTE"
            )

        # Create content state with all required fields
        content_state = {
            "status": journey_status,
            "track": (origin_stop.track if origin_stop and origin_stop.track else None),
            "currentStopName": (
                current_stop.station_name if current_stop else "Unknown"
            ),
            "nextStopName": next_stop.station_name if next_stop else None,
            "nextStopCode": next_stop.station_code if next_stop else None,
            "delayMinutes": calculated_delay,
            "journeyProgress": journey_progress,
            "dataTimestamp": int(time.time()),  # Unix timestamp for data freshness
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
            train_number=journey.train_id,
            # Progress tracking
            journey_progress=journey_progress,
            user_journey_stops=(
                len(user_journey_stops) if "user_journey_stops" in locals() else "N/A"
            ),
            # Departure/arrival data
            has_departed=has_train_departed,
            scheduled_departure_time=scheduled_departure_time,
            scheduled_arrival_time=scheduled_arrival_time,
            next_stop_arrival_time=next_stop_arrival_time,
            # Current state
            current_stop=(current_stop.station_name if current_stop else None),
            current_stop_code=(current_stop.station_code if current_stop else None),
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

        return content_state

    async def cleanup_expired_live_activity_tokens(self) -> None:
        """Clean up expired Live Activity tokens by marking them as inactive."""

        # Define the actual work as a nested function for freshness checking
        async def do_cleanup_work() -> None:
            try:
                logger.info("starting_live_activity_token_cleanup")

                # Use sync database access for consistency with other scheduler methods
                from sqlalchemy import update
                from sqlalchemy.orm import sessionmaker

                SyncSession = sessionmaker(self._get_sync_engine())

                with SyncSession() as session:
                    # Find expired tokens that are still active
                    current_time = now_et()

                    # Update expired tokens to inactive
                    result = cast(
                        CursorResult[tuple[()]],
                        session.execute(
                            update(LiveActivityToken)
                            .where(
                                and_(
                                    LiveActivityToken.is_active.is_(True),
                                    LiveActivityToken.expires_at <= current_time,
                                )
                            )
                            .values(is_active=False)
                        ),
                    )

                    session.commit()

                    cleaned_count = result.rowcount or 0
                    logger.info(
                        "live_activity_token_cleanup_completed",
                        tokens_cleaned=cleaned_count,
                        cutoff_time=current_time.isoformat(),
                    )

            except Exception as e:
                logger.error(
                    "live_activity_token_cleanup_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Use freshness check to prevent duplicate runs across replicas
        # This runs daily, so use a 23-hour minimum interval
        async with get_session() as db:
            safe_interval = calculate_safe_interval(24 * 60)  # 24 hours in minutes

            executed = await run_with_freshness_check(
                db=db,
                task_name="live_activity_token_cleanup",
                minimum_interval_seconds=safe_interval,
                task_func=do_cleanup_work,
            )

            if not executed:
                logger.debug("live_activity_token_cleanup_skipped_still_fresh")

    async def cleanup_old_locks(self) -> None:
        """Clean up old train locks to prevent memory leaks.

        This runs daily to remove locks for past journey dates that are no longer needed.
        """
        try:
            from trackrat.utils.locks import get_lock_manager

            lock_manager = get_lock_manager()
            removed_count = await lock_manager.cleanup_old_locks()

            logger.info(
                "lock_manager_cleanup_completed",
                removed_count=removed_count,
                status=lock_manager.get_status(),
            )
        except Exception as e:
            logger.error(
                "lock_manager_cleanup_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

    # All GTFS feed sources — add new systems here
    GTFS_SOURCES = ("NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY", "WMATA")

    async def refresh_gtfs_feeds(self) -> None:
        """Refresh GTFS static schedule data for all transit systems.

        This downloads and parses GTFS feeds to enable future date schedule queries.
        The GTFSService handles rate limiting (max once per 24 hours per source).
        """
        task_id = f"gtfs_refresh_{now_et().isoformat()}"

        async def do_gtfs_work() -> None:
            try:
                logger.info("starting_gtfs_feed_refresh")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                from trackrat.services.gtfs import GTFSService

                gtfs_service = GTFSService()

                results: dict[str, bool] = {}
                async with get_session() as db:
                    for source in self.GTFS_SOURCES:
                        result = await gtfs_service.refresh_feed(db, source)
                        results[source] = result
                        logger.info(
                            f"gtfs_{source.lower()}_refresh_complete",
                            refreshed=result,
                        )

                logger.info(
                    "gtfs_feed_refresh_complete",
                    **{f"{s.lower()}_refreshed": r for s, r in results.items()},
                )

            except Exception as e:
                logger.error(
                    "gtfs_feed_refresh_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        # GTFS refresh has built-in 24hr rate limiting, but add additional protection
        async with get_session() as db:
            safe_interval = calculate_safe_interval(12 * 60)  # 12 hours in minutes

            executed = await run_with_freshness_check(
                db=db,
                task_name="gtfs_feed_refresh",
                minimum_interval_seconds=safe_interval,
                task_func=do_gtfs_work,
            )

            if not executed:
                logger.debug("gtfs_feed_refresh_skipped_still_fresh")

    async def check_and_initialize_gtfs_feeds(self) -> None:
        """Check if GTFS data exists and trigger initial download if needed.

        Called on startup to ensure GTFS data is available for future date queries.
        Only triggers download if no data exists (empty database or first run).
        """
        try:
            from trackrat.services.gtfs import GTFSService

            gtfs_service = GTFSService()

            async with get_session() as db:
                availability: dict[str, bool] = {}
                for source in self.GTFS_SOURCES:
                    availability[source] = await gtfs_service.is_feed_available(
                        db, source
                    )

                if all(availability.values()):
                    logger.info(
                        "gtfs_data_already_available",
                        **{s.lower(): v for s, v in availability.items()},
                    )
                    return

                logger.info(
                    "gtfs_data_missing_triggering_initial_download",
                    **{f"{s.lower()}_available": v for s, v in availability.items()},
                )

                for source, available in availability.items():
                    if not available:
                        result = await gtfs_service.refresh_feed(db, source, force=True)
                        logger.info(
                            f"gtfs_{source.lower()}_initial_download_complete",
                            success=result,
                        )

        except Exception as e:
            logger.error(
                "gtfs_initialization_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't raise - this is a startup optimization, not a critical failure

    async def precompute_congestion_cache(self) -> None:
        """Pre-compute congestion API responses for common parameter combinations."""
        task_id = f"congestion_cache_{now_et().isoformat()}"

        # Define the actual work as a nested function for freshness checking
        async def do_cache_work() -> None:
            try:
                logger.info("starting_congestion_cache_precomputation")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Import here to avoid circular imports
                from trackrat.services.api_cache import ApiCacheService

                # Wrap in create_task to ensure fresh greenlet context.
                # APScheduler's AsyncIOExecutor doesn't reliably initialize
                # SQLAlchemy's greenlet bridge (same pattern as departure cache).
                async def _inner() -> None:
                    async with get_session() as session:
                        cache_service = ApiCacheService()

                        # Pre-compute congestion responses
                        await cache_service.precompute_congestion_responses(session)

                        # Clean up expired cache entries while we're here
                        deleted_count = await cache_service.cleanup_expired_cache(
                            session
                        )

                        if deleted_count > 0:
                            logger.info(
                                "cleaned_up_expired_api_cache_entries",
                                deleted_count=deleted_count,
                            )

                await asyncio.create_task(_inner())

                logger.info("congestion_cache_precomputation_completed")
            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        # This runs every 15 minutes, so use a 13-minute minimum interval
        async with get_session() as db:
            safe_interval = calculate_safe_interval(15)  # 15-minute scheduled interval

            executed = await run_with_freshness_check(
                db=db,
                task_name="congestion_cache_precompute",
                minimum_interval_seconds=safe_interval,
                task_func=do_cache_work,
            )

            if not executed:
                logger.debug("congestion_cache_precompute_skipped_still_fresh")

    async def precompute_departure_cache(self) -> None:
        """Pre-compute departure API responses for popular station pairs."""
        task_id = f"departure_cache_{now_et().isoformat()}"

        async def do_cache_work() -> None:
            try:
                logger.info("starting_departure_cache_precomputation")

                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                from trackrat.services.api_cache import ApiCacheService

                # Wrap in create_task to ensure fresh greenlet context
                # APScheduler's AsyncIOExecutor doesn't reliably initialize
                # SQLAlchemy's greenlet bridge (see also line 1734)
                async def _inner() -> None:
                    async with get_session() as session:
                        cache_service = ApiCacheService()
                        await cache_service.precompute_departure_responses(session)

                await asyncio.create_task(_inner())

                logger.info("departure_cache_precomputation_completed")
            finally:
                self._running_tasks.pop(task_id, None)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(2)  # Round up 1.5 to 2 minutes

            executed = await run_with_freshness_check(
                db=db,
                task_name="departure_cache_precompute",
                minimum_interval_seconds=safe_interval,
                task_func=do_cache_work,
            )

            if not executed:
                logger.debug("departure_cache_precompute_skipped_still_fresh")

    async def precompute_route_history_cache(self) -> None:
        """Pre-compute route history API responses for recently-requested param combinations."""
        task_id = f"route_history_cache_{now_et().isoformat()}"

        async def do_cache_work() -> None:
            try:
                logger.info("starting_route_history_cache_precomputation")

                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                from trackrat.services.api_cache import ApiCacheService

                async def _inner() -> None:
                    async with get_session() as session:
                        cache_service = ApiCacheService()
                        await cache_service.precompute_route_history_responses(session)

                await asyncio.create_task(_inner())

                logger.info("route_history_cache_precomputation_completed")
            finally:
                self._running_tasks.pop(task_id, None)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(5)  # 5-minute scheduled interval

            executed = await run_with_freshness_check(
                db=db,
                task_name="route_history_cache_precompute",
                minimum_interval_seconds=safe_interval,
                task_func=do_cache_work,
            )

            if not executed:
                logger.debug("route_history_cache_precompute_skipped_still_fresh")

    async def update_live_activities(self) -> None:
        """Update all active Live Activities with current train data."""
        task_id = f"live_activity_update_{now_et().isoformat()}"

        # Define the actual work as a nested function for freshness checking
        async def do_live_activity_work() -> None:
            try:
                logger.info("starting_live_activity_updates")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                from sqlalchemy import and_, select
                from sqlalchemy.orm import selectinload, sessionmaker

                # Use synchronous database access to avoid greenlet issues in scheduler context
                SyncSession = sessionmaker(self._get_sync_engine())

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
                            .options(
                                selectinload(TrainJourney.stops),
                                selectinload(TrainJourney.snapshots),
                            )
                        )

                        journey = session.scalar(journey_stmt)

                        if not journey:
                            logger.warning(
                                "journey_not_found_for_live_activity",
                                train_number=train_number,
                            )
                            continue

                        # Check if journey is expired, completed, or cancelled
                        # If so, send end events to all Live Activities tracking this train
                        should_end = (
                            journey.is_expired
                            or journey.is_completed
                            or journey.is_cancelled
                        )

                        if should_end:
                            end_reason = (
                                "expired"
                                if journey.is_expired
                                else (
                                    "completed" if journey.is_completed else "cancelled"
                                )
                            )

                            logger.info(
                                "live_activity_ending",
                                train_number=train_number,
                                reason=end_reason,
                                tokens_count=len(tokens),
                            )

                            # Send end event to each token
                            for token in tokens:
                                try:
                                    # Calculate final content state
                                    final_content_state = (
                                        self._calculate_live_activity_content_state(
                                            journey, token, session
                                        )
                                    )
                                    # Add end reason to content state
                                    final_content_state["endReason"] = end_reason

                                    if self.apns_service:
                                        await self.apns_service.send_live_activity_end(
                                            token.push_token, final_content_state
                                        )

                                    # Mark token as inactive since Live Activity is ending
                                    token.is_active = False
                                    session.commit()

                                except Exception as e:
                                    logger.error(
                                        "live_activity_end_failed",
                                        train_number=train_number,
                                        error=str(e),
                                        error_type=type(e).__name__,
                                    )

                            continue  # Skip normal update processing

                        # Force JIT refresh for trains with active LAs awaiting track assignment
                        # This ensures we poll the transit API every LA cycle (~1 min) for
                        # trains approaching departure without a track, rather than waiting
                        # for the normal staleness threshold (~60s).
                        force_refresh_for_track = False
                        if journey.data_source in ("NJT", "LIRR", "MNR"):
                            for t in tokens:
                                if t.track_notified_at is not None:
                                    continue
                                origin_stop = next(
                                    (
                                        s
                                        for s in (journey.stops or [])
                                        if s.station_code == t.origin_code
                                    ),
                                    None,
                                )
                                if not origin_stop or origin_stop.track:
                                    continue  # Already has track or stop not found
                                dep_time = (
                                    origin_stop.updated_departure
                                    or origin_stop.scheduled_departure
                                )
                                if (
                                    dep_time
                                    and (
                                        ensure_timezone_aware(dep_time) - now_et()
                                    ).total_seconds()
                                    < 1800
                                ):
                                    force_refresh_for_track = True
                                    logger.info(
                                        "force_refresh_for_track_assignment",
                                        train_number=train_number,
                                        origin_code=t.origin_code,
                                    )
                                    break

                        # Check if journey data is stale (>60 seconds old)
                        if (
                            force_refresh_for_track
                            or journey.last_updated_at is None
                            or self._is_stale(
                                ensure_timezone_aware(journey.last_updated_at)
                            )
                        ):
                            logger.info(
                                "live_activity_journey_stale",
                                train_number=train_number,
                                last_updated=(
                                    ensure_timezone_aware(
                                        journey.last_updated_at
                                    ).isoformat()
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
                                            # Remove stale journey from session identity map
                                            # so we get fresh data including updated stops
                                            # (session.refresh doesn't reload eagerly-loaded relationships)
                                            session.expunge(journey)
                                            # Re-query to get fresh data from database
                                            refreshed_journey_obj = session.scalar(
                                                journey_stmt
                                            )
                                            if refreshed_journey_obj:
                                                journey = refreshed_journey_obj
                                                logger.info(
                                                    "live_activity_journey_refreshed",
                                                    train_number=train_number,
                                                    new_last_updated=(
                                                        ensure_timezone_aware(
                                                            journey.last_updated_at
                                                        ).isoformat()
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

                        # Process each token individually to calculate personalized content state
                        for token in tokens:
                            try:
                                # Calculate content state specific to this token's journey segment
                                content_state = (
                                    self._calculate_live_activity_content_state(
                                        journey, token, session
                                    )
                                )

                                # Inject alertMetadata when track is newly assigned
                                track_just_assigned = (
                                    content_state.get("track") is not None
                                    and token.track_notified_at is None
                                )
                                if track_just_assigned:
                                    content_state["alertMetadata"] = {
                                        "alert_type": "track_assigned",
                                        "train_id": journey.train_id,
                                        "dynamic_island_priority": "high",
                                    }
                                    logger.info(
                                        "track_assignment_notification",
                                        train_number=train_number,
                                        track=content_state["track"],
                                        origin_code=token.origin_code,
                                    )

                                # Send token-specific update via APNS
                                success = (
                                    await self.apns_service.send_live_activity_update(
                                        token.push_token, content_state
                                    )
                                )

                                if success and track_just_assigned:
                                    token.track_notified_at = now_et()
                                    session.commit()

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

            except Exception as e:
                # Add more context for debugging
                try:
                    import greenlet  # type: ignore[import-untyped]

                    greenlet_info = str(greenlet.getcurrent())
                except ImportError:
                    greenlet_info = "greenlet not available"

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
                    greenlet_current=greenlet_info,
                )
            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check to prevent duplicate runs across replicas
        # Live Activities update every 30 seconds, so use a 25-second minimum interval
        async with get_session() as db:
            safe_interval = 25  # 25 seconds (slightly less than 30 to ensure updates)

            executed = await run_with_freshness_check(
                db=db,
                task_name="live_activity_updates",
                minimum_interval_seconds=safe_interval,
                task_func=do_live_activity_work,
            )

            if not executed:
                logger.debug("live_activity_updates_skipped_still_fresh")

    async def run_train_validation(self) -> None:
        """Run end-to-end validation of train discovery and API accessibility."""
        task_id = f"train_validation_{now_et().isoformat()}"

        async def do_validation_work() -> None:
            """The actual validation work."""
            try:
                logger.info("starting_train_validation_task")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Import and run validation
                # Create session here (before HTTP I/O) to avoid greenlet issues
                # when _save_validation_result needs DB access deep in the call chain
                from trackrat.services.validation import TrainValidationService

                async with get_session() as validation_db:
                    async with TrainValidationService(self.settings) as validator:
                        results = await validator.run_validation(db=validation_db)

                        # Summary metrics
                        total_missing = sum(len(r.missing_trains) for r in results)
                        routes_with_issues = sum(1 for r in results if r.missing_trains)

                        logger.info(
                            "train_validation_completed",
                            total_routes_checked=len(results),
                            routes_with_issues=routes_with_issues,
                            total_missing_trains=total_missing,
                        )

            except Exception as e:
                logger.error(
                    "train_validation_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check with 55-minute interval (for hourly runs)
        async with get_session() as db:
            safe_interval = 55 * 60  # 55 minutes

            executed = await run_with_freshness_check(
                db=db,
                task_name="train_validation",
                minimum_interval_seconds=safe_interval,
                task_func=do_validation_work,
            )

            if not executed:
                logger.debug("train_validation_skipped_still_fresh")

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

    async def collect_njt_schedules(self) -> None:
        """Collect NJT schedule data once daily at 12:30 AM.

        This task fetches 27-hour schedule data from NJ Transit API
        and creates SCHEDULED journey records for trains that haven't
        been observed yet.
        """
        task_id = f"njt_schedules_{now_et().isoformat()}"

        async def do_schedule_collection() -> None:
            """The actual schedule collection work."""
            try:
                logger.info("starting_njt_schedule_collection_task")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Ensure NJT client is initialized
                if not self.njt_client:
                    raise RuntimeError(
                        "NJTransitClient not initialized - call start() first"
                    )

                # Run schedule collection
                collector = NJTScheduleCollector(self.njt_client)
                result = await collector.collect_all_schedules()

                logger.info(
                    "njt_schedule_collection_completed",
                    total_schedules=result.get("total_schedules", 0),
                    new_schedules=result.get("new_schedules", 0),
                    updated_schedules=result.get("updated_schedules", 0),
                    skipped_observed=result.get("skipped_observed", 0),
                    errors=result.get("errors", 0),
                )

            except Exception as e:
                logger.error(
                    "njt_schedule_collection_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check with 23-hour minimum interval (safe for once-daily task)
        async with get_session() as db:
            executed = await run_with_freshness_check(
                db=db,
                task_name="njt_schedule_collection",
                minimum_interval_seconds=23 * 60 * 60,  # 23 hours
                task_func=do_schedule_collection,
            )

            if not executed:
                logger.debug("njt_schedule_collection_skipped_still_fresh")

    async def generate_amtrak_schedules(self) -> None:
        """Generate Amtrak schedules based on historical patterns.

        This task runs daily at 12:45 AM and analyzes the past 22 days of
        Amtrak train data to identify patterns and create SCHEDULED journey
        records for trains that are expected to run today.
        """
        task_id = f"amtrak_schedules_{now_et().isoformat()}"

        async def do_schedule_generation() -> None:
            """The actual schedule generation work."""
            try:
                logger.info("starting_amtrak_schedule_generation_task")

                # Track running task
                task = asyncio.current_task()
                if task:
                    self._running_tasks[task_id] = task

                # Create the pattern scheduler
                pattern_scheduler = AmtrakPatternScheduler()

                # Generate schedules for today
                today = now_et().date()
                result = await pattern_scheduler.generate_daily_schedules(today)

                logger.info(
                    "amtrak_schedule_generation_completed",
                    created=result.get("created", 0),
                    updated=result.get("updated", 0),
                    skipped=result.get("skipped", 0),
                    errors=result.get("errors", 0),
                    target_date=today.isoformat(),
                )

                # Also generate for tomorrow for better planning
                tomorrow = today + timedelta(days=1)
                tomorrow_result = await pattern_scheduler.generate_daily_schedules(
                    tomorrow
                )

                logger.info(
                    "amtrak_tomorrow_schedule_generation_completed",
                    created=tomorrow_result.get("created", 0),
                    updated=tomorrow_result.get("updated", 0),
                    skipped=tomorrow_result.get("skipped", 0),
                    errors=tomorrow_result.get("errors", 0),
                    target_date=tomorrow.isoformat(),
                )

                # Clean up old scheduled records that never became observed
                deleted_count = await pattern_scheduler.cleanup_old_scheduled_records(
                    days_to_keep=1
                )

                logger.info(
                    "amtrak_schedule_cleanup_completed",
                    deleted_count=deleted_count,
                )

            except Exception as e:
                logger.error(
                    "amtrak_schedule_generation_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

        # Use freshness check with 23-hour minimum interval (safe for once-daily task)
        async with get_session() as db:
            executed = await run_with_freshness_check(
                db=db,
                task_name="amtrak_schedule_generation",
                minimum_interval_seconds=23 * 60 * 60,  # 23 hours
                task_func=do_schedule_generation,
            )

            if not executed:
                logger.debug("amtrak_schedule_generation_skipped_still_fresh")

    async def run_alert_evaluation(self) -> None:
        """Evaluate route alert subscriptions and send notifications."""

        async def do_alert_evaluation_work() -> None:
            if not self.apns_service:
                logger.debug("alert_evaluation_skipped_no_apns")
                return

            async with get_session() as session:
                await evaluate_route_alerts(session, self.apns_service)

            # Also evaluate service alerts (planned work) in the same cycle
            async with get_session() as session:
                await evaluate_service_alerts(session, self.apns_service)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(5)

            executed = await run_with_freshness_check(
                db=db,
                task_name="route_alert_evaluation",
                minimum_interval_seconds=safe_interval,
                task_func=do_alert_evaluation_work,
            )

            if not executed:
                logger.debug("route_alert_evaluation_skipped_still_fresh")

    async def run_morning_digest_evaluation(self) -> None:
        """Evaluate morning digest subscriptions and send notifications."""

        async def do_digest_work() -> None:
            if not self.apns_service:
                logger.debug("morning_digest_skipped_no_apns")
                return

            async with get_session() as session:
                await evaluate_morning_digests(session, self.apns_service)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(5)

            executed = await run_with_freshness_check(
                db=db,
                task_name="morning_digest_evaluation",
                minimum_interval_seconds=safe_interval,
                task_func=do_digest_work,
            )

            if not executed:
                logger.debug("morning_digest_evaluation_skipped_still_fresh")

    async def run_service_alerts_collection(self) -> None:
        """Collect service alerts from MTA GTFS-RT feeds and NJT API."""

        async def do_service_alerts_work() -> None:
            result = await collect_service_alerts()
            logger.info("service_alerts_collection_complete", stats=result)

        async with get_session() as db:
            safe_interval = calculate_safe_interval(15)

            executed = await run_with_freshness_check(
                db=db,
                task_name="service_alerts_collection",
                minimum_interval_seconds=safe_interval,
                task_func=do_service_alerts_work,
            )

            if not executed:
                logger.debug("service_alerts_collection_skipped_still_fresh")

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
