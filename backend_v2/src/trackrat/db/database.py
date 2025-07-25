"""
Database initialization with backup support.
"""

import logging

from trackrat.services.backup_service import BackupService
from trackrat.settings import get_settings

from .engine import get_engine
from .migrations_runner import run_migrations

logger = logging.getLogger(__name__)

# Global backup service instance
backup_service: BackupService | None = None


def get_database_path() -> str | None:
    """Extract database file path from database URL."""
    settings = get_settings()
    db_url = str(settings.database_url)

    if "sqlite" not in db_url:
        return None

    # Handle different SQLite URL formats
    if ":///" in db_url:
        # sqlite+aiosqlite:///path/to/db.db
        path = db_url.split("///", 1)[1]
    elif "://" in db_url:
        # sqlite://path/to/db.db
        path = db_url.split("://", 1)[1]
    else:
        # Just a file path
        path = db_url

    return path


async def init_database_with_backup() -> None:
    """Initialize database with backup support."""
    global backup_service

    settings = get_settings()

    # Only set up backup if bucket is configured and using SQLite
    if settings.gcs_backup_bucket and settings.is_sqlite:
        db_path = get_database_path()
        if db_path:
            try:
                backup_service = BackupService(
                    db_path, settings.gcs_backup_bucket, settings.environment
                )

                # Try to restore from backup
                restored = await backup_service.restore_from_backup()
                if restored:
                    logger.info("Database restored from backup")
                else:
                    logger.info("No backup found, starting with fresh database")

                # Start periodic backup
                await backup_service.start_periodic_backup(
                    settings.backup_interval_seconds
                )
                logger.info(
                    f"Started periodic backup every {settings.backup_interval_seconds}s"
                )

            except Exception as e:
                logger.error(f"Failed to initialize backup service: {e}")
                backup_service = None
    else:
        if not settings.gcs_backup_bucket:
            logger.info("No GCS backup bucket configured, backup disabled")
        elif not settings.is_sqlite:
            logger.info("Not using SQLite, backup not supported")

    # Initialize the database engine (this ensures tables are created)
    get_engine()

    # Run migrations AFTER backup restore to ensure we're migrating the restored database
    logger.info("Running database migrations after backup restore")
    await run_migrations()


async def shutdown_database() -> None:
    """Shutdown database with final backup."""
    global backup_service

    if backup_service:
        try:
            # Create final backup
            await backup_service.create_backup()
            logger.info("Created final backup before shutdown")

            # Stop periodic backup
            await backup_service.stop_periodic_backup()
            logger.info("Stopped periodic backup")

        except Exception as e:
            logger.error(f"Error during backup shutdown: {e}")
        finally:
            backup_service = None


def get_backup_service() -> BackupService | None:
    """Get the global backup service instance."""
    return backup_service
