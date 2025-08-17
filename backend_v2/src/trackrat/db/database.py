"""
PostgreSQL database initialization.

Cloud SQL PostgreSQL provides automated backups, so no manual backup service is needed.
"""

import logging

from .engine import get_engine
from .migrations_runner import run_migrations

logger = logging.getLogger(__name__)


async def init_database() -> None:
    """Initialize PostgreSQL database and run migrations."""
    # Initialize the database engine
    logger.info("Initializing PostgreSQL database engine")
    get_engine()
    logger.info("Database engine initialized")

    # Run migrations to ensure schema is up to date
    logger.info("Running database migrations")
    await run_migrations()
    logger.info("Database migrations completed")


async def shutdown_database() -> None:
    """Shutdown database connections."""
    from .engine import close_engine

    logger.info("Shutting down database connections")
    await close_engine()
    logger.info("Database shutdown completed")
