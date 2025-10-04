"""
Structured logging configuration for TrackRat V2.

Uses structlog for better cloud-native logging with context preservation.
"""

import logging
import sys

import structlog
from structlog.types import EventDict, Processor

from trackrat.settings import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Disable verbose httpx logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Disable verbose database operation logs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)

    # Suppress noisy APScheduler logs (Phase 1: only show warnings and errors)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    # Suppress uvicorn access logs for health checks (will handle in middleware)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # Processors for structlog
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add context vars
    processors.append(add_app_context)

    # Use JSON in production, console in development
    if settings.environment == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to all log entries."""
    settings = get_settings()
    event_dict["environment"] = settings.environment
    event_dict["service"] = "trackrat-v2"
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
