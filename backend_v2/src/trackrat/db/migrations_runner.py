"""
Database migrations runner for TrackRat V2.

This module handles running Alembic migrations programmatically
after backup restore to ensure proper migration ordering.
"""

from pathlib import Path

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
    Run database migrations using Alembic in a subprocess.

    This runs migrations in a separate process to avoid async/sync conflicts
    that occur when running synchronous Alembic operations within an async context.
    """
    import os
    import subprocess
    import sys

    # Allow skipping migrations in development for debugging
    if os.getenv("TRACKRAT_SKIP_MIGRATIONS") == "true":
        logger.warning(
            "Skipping database migrations due to TRACKRAT_SKIP_MIGRATIONS=true"
        )
        return

    try:
        logger.info("Running database migrations")

        # Get the backend_v2 directory (where alembic.ini lives)
        # migrations_runner.py is in src/trackrat/db/
        current_dir = Path(__file__).parent  # src/trackrat/db
        backend_dir = current_dir.parent.parent.parent  # backend_v2

        # Verify alembic.ini exists
        alembic_ini = backend_dir / "alembic.ini"
        if not alembic_ini.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

        # Build the alembic command
        # Using sys.executable ensures we use the same Python interpreter
        alembic_cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]

        # Set up environment for the subprocess
        env = os.environ.copy()
        settings = get_settings()
        # Alembic expects DATABASE_URL or we need to pass it via -x option
        # Using DATABASE_URL is simpler and more standard
        env["DATABASE_URL"] = settings.database_url_sync

        logger.info(
            f"Executing alembic upgrade head in subprocess (cwd: {backend_dir})"
        )

        # Run migrations with a reasonable timeout
        try:
            result = subprocess.run(
                alembic_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for data-heavy backfill migrations
                cwd=str(backend_dir),  # Run from backend_v2 directory
                check=False,  # We'll check returncode ourselves for better error messages
            )

            # Log the output for debugging
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        logger.debug(f"Migration output: {line}")

            # Log any stderr output (Alembic logs to stderr by default)
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if line:
                        # Alembic INFO logs go to stderr, so don't treat as warning
                        if "INFO" in line:
                            logger.debug(f"Migration info: {line}")
                        else:
                            logger.warning(f"Migration warning: {line}")

            # Check if the command succeeded
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(
                    f"Migration failed with exit code {result.returncode}: {error_msg}"
                )

            logger.info("Alembic upgrade completed successfully")

        except subprocess.TimeoutExpired as err:
            logger.error("Database migrations timed out after 600 seconds")
            raise RuntimeError(
                "Migration timeout - possible database connection issue"
            ) from err

        # Optionally verify the migration version (now async-safe)
        await verify_migration_version()

        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        # Re-raise the exception as migrations are critical
        raise


async def verify_migration_version() -> None:
    """
    Verify the current migration version after subprocess completion.

    This uses the async engine to check the migration version,
    avoiding any sync/async conflicts.
    """
    try:
        from sqlalchemy import text

        from trackrat.db.engine import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.first()
            if row:
                logger.info(f"Database is now at migration version: {row[0]}")
            else:
                logger.warning("No migration version found in alembic_version table")
    except Exception as e:
        # This is non-critical, so just log it
        logger.debug(f"Could not verify migration version: {e}")
