"""
Main FastAPI application for TrackRat V2.

This module sets up the FastAPI app with all routers, middleware, and lifecycle events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import time
from typing import Callable
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog
from structlog import get_logger

from trackrat.api import (
    health,
    live_activities,
    predictions,
    routes,
    trains,
    validation,
)
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


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    """Add correlation ID to all requests for tracing."""
    # Generate or get correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4())[:8])

    # Bind to structlog context for this request
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # Add to request state for access in handlers
    request.state.correlation_id = correlation_id

    # Process request
    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response


@app.middleware("http")
async def suppress_health_check_logs(request: Request, call_next: Callable) -> Response:
    """Middleware to suppress logging for health check endpoints."""
    # List of paths that should not be logged
    quiet_paths = {"/health", "/health/live", "/health/ready", "/metrics"}

    # Check if this is a path we want to suppress logs for
    should_suppress = request.url.path in quiet_paths

    # For health checks, we'll handle logging ourselves (or not log at all)
    if should_suppress:
        # Process the request without logging
        response = await call_next(request)
        # Only log if there was an error
        if response.status_code >= 400:
            logger.warning(
                "health_check_failed",
                path=request.url.path,
                status_code=response.status_code,
                method=request.method,
            )
        return response

    # For all other requests, process normally (will be logged by uvicorn)
    return await call_next(request)


# Include routers
app.include_router(trains.router)
app.include_router(health.router)
app.include_router(live_activities.router)
app.include_router(predictions.router)
app.include_router(routes.router)
app.include_router(validation.router)

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
