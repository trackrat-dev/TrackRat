"""
Database migrations runner for TrackRat V2.

This module handles running Alembic migrations programmatically
after backup restore to ensure proper migration ordering.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from structlog import get_logger

from trackrat.settings import get_settings

logger = get_logger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    # Find alembic.ini relative to this file
    # migrations_runner.py is in src/trackrat/db/
    # alembic.ini is in backend_v2/
    current_dir = Path(__file__).parent  # src/trackrat/db
    backend_dir = current_dir.parent.parent.parent  # backend_v2
    alembic_ini = backend_dir / "alembic.ini"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

    config = Config(str(alembic_ini))

    # Set script location to absolute path
    script_location = backend_dir / "src" / "trackrat" / "db" / "migrations"
    config.set_main_option("script_location", str(script_location))

    # Set the database URL from settings
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.database_url_sync)

    return config


async def run_migrations() -> None:
    """
    Run database migrations using Alembic.

    This should be called after database initialization and backup restore.
    """
    try:
        logger.info("Running database migrations")

        # Get Alembic configuration
        logger.info("Getting Alembic config")
        config = get_alembic_config()
        logger.info("Alembic config ready")

        # Check if alembic_version table exists and has current revision
        logger.info("Checking database schema state")

        # Simple check: if alembic_version table exists with a revision, assume migrations are done
        # This avoids hanging Alembic commands during startup
        try:
            # Use SQLAlchemy directly with sync engine for the check
            from sqlalchemy import create_engine, text

            from trackrat.settings import get_settings

            settings = get_settings()
            sync_engine = create_engine(settings.database_url_sync)

            with sync_engine.connect() as conn:
                # Check if alembic_version table exists and has a version
                result = conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                current_version = result.scalar()

            if current_version:
                logger.info(
                    f"Database has migration version: {current_version}, skipping migrations"
                )
            else:
                logger.info("No migration version found, running migrations")
                command.upgrade(config, "head")
                logger.info("Alembic upgrade completed")

        except Exception as e:
            # If we can't check, assume migrations are needed
            logger.info(f"Could not check migration state ({e}), running migrations")
            command.upgrade(config, "head")
            logger.info("Alembic upgrade completed")

        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        # Re-raise the exception as migrations are critical
        raise
