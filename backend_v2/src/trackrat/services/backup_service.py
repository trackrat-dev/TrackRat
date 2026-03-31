"""
SQLite database backup service for Cloud Storage.
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from google.cloud import storage  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class BackupService:
    """Service for backing up SQLite database to Google Cloud Storage."""

    def __init__(self, db_path: str, bucket_name: str, environment: str = "dev"):
        """
        Initialize backup service.

        Args:
            db_path: Local path to SQLite database file
            bucket_name: GCS bucket name for backups
            environment: Environment name for backup naming
        """
        self.db_path = Path(db_path)
        self.bucket_name = bucket_name
        self.environment = environment
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self._backup_task: asyncio.Task[Any] | None = None
        self._stop_backup = False

    async def restore_from_backup(self) -> bool:
        """
        Restore database from latest backup in GCS.

        Returns:
            True if backup was restored, False if no backup found
        """
        try:
            # Check if backup exists
            blob = self.bucket.blob("latest.db")
            if not blob.exists():
                logger.info("No backup found in GCS, starting with fresh database")
                return False

            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Download backup to temporary file first for safety
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                blob.download_to_filename(str(temp_path))

            # Atomically move temp file to final location
            shutil.move(str(temp_path), str(self.db_path))

            logger.info("Successfully restored database from backup")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            # Clean up temp file if it exists
            try:
                if "temp_path" in locals():
                    temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return False

    async def create_backup(self) -> bool:
        """
        Create backup of current database.

        Returns:
            True if backup succeeded, False otherwise
        """
        if not self.db_path.exists():
            logger.warning(
                f"Database file {self.db_path} does not exist, skipping backup"
            )
            return False

        try:
            await self._upload_file("latest.db")

            logger.info("Successfully created backup: latest.db")
            return True

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    async def _upload_file(self, blob_name: str) -> None:
        """Upload database file to GCS with the given blob name."""
        blob = self.bucket.blob(blob_name)

        # Use a temporary copy to avoid locking issues
        with tempfile.NamedTemporaryFile() as temp_file:
            shutil.copy2(str(self.db_path), temp_file.name)
            blob.upload_from_filename(temp_file.name)

    async def start_periodic_backup(self, interval: int | None = None) -> None:
        """
        Start periodic backup task.

        Args:
            interval: Backup interval in seconds (default from settings)
        """
        if self._backup_task and not self._backup_task.done():
            logger.warning("Periodic backup already running")
            return

        if interval is None:
            interval = 300  # Default 5 minutes

        self._stop_backup = False
        self._backup_task = asyncio.create_task(self._backup_loop(interval))
        logger.info(f"Started periodic backup with {interval}s interval")

    async def stop_periodic_backup(self) -> None:
        """Stop periodic backup task."""
        self._stop_backup = True
        if self._backup_task and not self._backup_task.done():
            try:
                await asyncio.wait_for(self._backup_task, timeout=5.0)
            except TimeoutError:
                self._backup_task.cancel()
                try:
                    await self._backup_task
                except asyncio.CancelledError:
                    pass
            logger.info("Stopped periodic backup")

    async def _backup_loop(self, interval: int) -> None:
        """Internal periodic backup loop."""
        while not self._stop_backup:
            try:
                await self.create_backup()
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")

            # Wait for interval or until stop signal
            try:
                await asyncio.wait_for(
                    asyncio.Event().wait(), timeout=interval  # Wait indefinitely
                )
            except TimeoutError:
                # Normal timeout, continue loop
                continue
            except asyncio.CancelledError:
                break
