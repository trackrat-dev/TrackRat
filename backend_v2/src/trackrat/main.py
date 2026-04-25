"""
Main FastAPI application for TrackRat V2.

This module sets up the FastAPI app with all routers, middleware, and lifecycle events.
"""

import time
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.gzip import GZipMiddleware
from structlog import get_logger

from trackrat.api import (
    admin,
    alerts,
    feedback,
    health,
    live_activities,
    predictions,
    route_preferences,
    routes,
    share,
    trains,
    trips,
    validation,
)
from trackrat.db.database import init_database, shutdown_database
from trackrat.db.engine import close_engine, get_session
from trackrat.services.apns import SimpleAPNSService
from trackrat.services.scheduler import get_scheduler
from trackrat.settings import get_settings
from trackrat.utils.logging import setup_logging
from trackrat.utils.request_stats import get_request_stats

# Set up logging first
setup_logging()
logger = get_logger(__name__)


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


_STAGING_DEVICE_TOKEN_THRESHOLD = 50


async def _check_staging_notification_safety(settings: Any) -> bool:
    """Check if staging database contains production notification data.

    After cloning production to staging, the scrub script should have cleared
    device_tokens and live_activity_tokens. If they still contain many rows,
    it means the scrub was skipped or failed, and the scheduler would send
    push notifications to real production users.

    Returns True if APNS should be disabled (unsafe token count detected).
    """
    from sqlalchemy import func, select

    from trackrat.models.database import DeviceToken, LiveActivityToken

    try:
        async with get_session() as session:
            device_count = await session.scalar(
                select(func.count()).select_from(DeviceToken)
            )
            la_count = await session.scalar(
                select(func.count()).select_from(LiveActivityToken)
            )

        if (device_count or 0) > _STAGING_DEVICE_TOKEN_THRESHOLD:
            logger.critical(
                "staging_notification_safety_warning",
                message=(
                    f"Staging database contains {device_count} device tokens and "
                    f"{la_count} Live Activity tokens. This likely means the "
                    "post-clone scrub did not run. APNS will be disabled to "
                    "prevent sending notifications to production users."
                ),
                device_tokens=device_count,
                live_activity_tokens=la_count,
                threshold=_STAGING_DEVICE_TOKEN_THRESHOLD,
            )
            return True
        elif (device_count or 0) > 0 or (la_count or 0) > 0:
            logger.info(
                "staging_notification_tokens_present",
                device_tokens=device_count,
                live_activity_tokens=la_count,
                message="Small number of tokens present — likely from staging testers.",
            )
        else:
            logger.info(
                "staging_notification_safety_ok",
                message="No production tokens in staging database.",
            )
    except Exception as e:
        logger.warning(
            "staging_notification_safety_check_failed",
            error=str(e),
            message="Could not verify staging notification safety. Proceeding with caution.",
        )

    return False


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

    # Defensive check: warn if staging has production notification data.
    # If the post-clone scrub was skipped, disable APNS to prevent sending
    # push notifications to production users.
    disable_apns = False
    if settings.environment == "staging":
        disable_apns = await _check_staging_notification_safety(settings)

    # Initialize APNS service
    logger.info("initializing_apns_service")
    if disable_apns:
        apns_service = None
        logger.critical(
            "apns_disabled_for_safety",
            message="APNS disabled on staging due to unscrubbed production tokens.",
        )
    else:
        apns_service = SimpleAPNSService()
        logger.info(
            "apns_service_initialized",
            is_configured=apns_service.is_configured,
            environment=settings.environment,
            apns_environment=settings.apns_environment,
            apns_base_url=apns_service.base_url,
        )

    # Store APNS service on app state for use by other routers
    app.state.apns_service = apns_service

    # Start scheduler with APNS service (None = no notification jobs)
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
    description="Train tracking and forecasting system for NJ Transit, Amtrak, PATH, Metro North, LIRR, and more!",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=500)

# Allow all origins — public API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Coroutine[Any, Any, Response]]
) -> Response:
    """Add correlation ID to all requests for tracing."""
    # Generate or get correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4())[:8])

    # Bind to structlog context for this request
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # Add to request state for access in handlers
    request.state.correlation_id = correlation_id

    # Process request
    response: Response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response


@app.middleware("http")
async def suppress_health_check_logs(
    request: Request, call_next: Callable[[Request], Coroutine[Any, Any, Response]]
) -> Response:
    """Middleware to suppress logging for health check endpoints."""
    # List of paths that should not be logged
    quiet_paths = {"/health", "/health/live", "/health/ready", "/metrics"}

    # Check if this is a path we want to suppress logs for
    should_suppress = request.url.path in quiet_paths

    # For health checks, we'll handle logging ourselves (or not log at all)
    if should_suppress:
        # Process the request without logging
        response: Response = await call_next(request)
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


@app.middleware("http")
async def request_stats_middleware(
    request: Request, call_next: Callable[[Request], Coroutine[Any, Any, Response]]
) -> Response:
    """Track inbound request metrics for the admin stats page."""
    start = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start

    # Extract the matched route template (e.g. "/api/v2/trains/{train_id}")
    route = request.scope.get("route")
    path_template = route.path if route and hasattr(route, "path") else request.url.path

    # Skip noisy internal paths
    if path_template not in {"/health", "/health/live", "/health/ready", "/metrics"}:
        query_params = dict(request.query_params)
        # Prefer X-Forwarded-For (set by GCP load balancer) over direct client IP
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[
            0
        ].strip() or (request.client.host if request.client else "unknown")
        get_request_stats().record_request(
            path_template=path_template,
            status_code=response.status_code,
            user_agent=request.headers.get("user-agent", ""),
            duration=duration,
            client_ip=client_ip,
            query_params=query_params if query_params else None,
        )

    return response


# Include routers
app.include_router(admin.router, include_in_schema=False)
app.include_router(alerts.router, include_in_schema=False)
app.include_router(feedback.router, include_in_schema=False)
app.include_router(health.router, include_in_schema=False)
app.include_router(live_activities.router, include_in_schema=False)
app.include_router(predictions.router)
app.include_router(route_preferences.router, include_in_schema=False)
app.include_router(routes.router)
app.include_router(share.router)
app.include_router(trains.router)
app.include_router(trips.router)
app.include_router(validation.router, include_in_schema=False)

# Prometheus metrics endpoint (direct route avoids Starlette mount 307 redirect)
settings = get_settings()
if settings.enable_metrics:

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        from trackrat.utils.metrics import update_system_metrics

        update_system_metrics()
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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


# Apple Universal Links: tells iOS that taps on apiv2.trackrat.net/share/train/*
# should open the TrackRat iOS app instead of Safari. The app's entitlement must
# include `applinks:apiv2.trackrat.net` for Apple to fetch this file.
_AASA_PAYLOAD: dict[str, object] = {
    "applinks": {
        "details": [
            {
                "appIDs": ["D5RZZ55J9R.net.trackrat.TrackRat"],
                "components": [
                    {
                        "/": "/share/train/*",
                        "comment": "Share-link previews open in the iOS app",
                    },
                ],
            }
        ]
    }
}


@app.get("/.well-known/apple-app-site-association", include_in_schema=False)
async def apple_app_site_association() -> Response:
    """Serve the AASA file for Universal Link routing.

    Must be served over HTTPS without redirects with ``Content-Type: application/json``
    (Apple's crawler is strict about both).
    """
    import json as _json

    return Response(
        content=_json.dumps(_AASA_PAYLOAD),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )
