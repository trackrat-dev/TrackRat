"""
Main FastAPI application for TrackRat V2.

This module sets up the FastAPI app with all routers, middleware, and lifecycle events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from structlog import get_logger

from trackrat.api import health, live_activities, routes, trains
from trackrat.db.database import init_database, shutdown_database
from trackrat.db.engine import close_engine
from trackrat.services.apns import SimpleAPNSService
from trackrat.services.scheduler import get_scheduler
from trackrat.settings import get_settings
from trackrat.utils.logging import setup_logging

# Set up logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events."""
    settings = get_settings()

    logger.info(
        "starting_trackrat_v2", environment=settings.environment, debug=settings.debug
    )

    # Initialize PostgreSQL database
    logger.info("starting_database_initialization")
    await init_database()
    logger.info("database_initialization_complete")

    # Initialize APNS service
    logger.info("initializing_apns_service")
    apns_service = SimpleAPNSService()
    logger.info(
        "apns_service_initialized",
        is_configured=apns_service.is_configured,
        environment=settings.environment,
        apns_environment=settings.apns_environment,
        apns_base_url=apns_service.base_url,
    )

    # Start scheduler with APNS service
    logger.info("starting_scheduler_from_lifespan")
    scheduler = get_scheduler(apns_service=apns_service)
    await scheduler.start()
    logger.info("scheduler_started_from_lifespan")

    logger.info("trackrat_v2_started")

    yield

    # Cleanup
    logger.info("shutting_down_trackrat_v2")

    # Stop scheduler
    await scheduler.stop()

    # Shutdown database with final backup
    await shutdown_database()

    # Close database connections
    await close_engine()

    logger.info("trackrat_v2_shutdown_complete")


# Create FastAPI app
app = FastAPI(
    title="TrackRat V2 API",
    description="Simplified train tracking system for NJ Transit",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(trains.router)
app.include_router(health.router)
app.include_router(live_activities.router)

app.include_router(routes.router)

# Mount Prometheus metrics endpoint if enabled
settings = get_settings()
if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "TrackRat V2",
        "version": "2.0.0",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health",
    }
