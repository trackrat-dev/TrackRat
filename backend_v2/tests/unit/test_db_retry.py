"""
Tests for database retry logic in trackrat.db.engine.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from trackrat.db.engine import retry_on_deadlock, _is_postgresql_concurrency_error


class TestIsPostgresqlConcurrencyError:
    """Tests for _is_postgresql_concurrency_error function."""

    def test_detects_deadlock(self):
        """Should detect deadlock errors."""
        error = Exception("deadlock detected")
        assert _is_postgresql_concurrency_error(error) is True

    def test_detects_deadlock_case_insensitive(self):
        """Should detect deadlock errors regardless of case."""
        error = Exception("DEADLOCK DETECTED in transaction")
        assert _is_postgresql_concurrency_error(error) is True

    def test_detects_connection_reset(self):
        """Should detect connection reset errors."""
        error = Exception("connection reset by peer")
        assert _is_postgresql_concurrency_error(error) is True

    def test_detects_serialization_error(self):
        """Should detect serialization errors."""
        error = Exception("could not serialize access due to concurrent update")
        assert _is_postgresql_concurrency_error(error) is True

    def test_ignores_other_errors(self):
        """Should not flag unrelated errors."""
        error = Exception("syntax error at or near SELECT")
        assert _is_postgresql_concurrency_error(error) is False

    def test_ignores_empty_error(self):
        """Should handle empty error messages."""
        error = Exception("")
        assert _is_postgresql_concurrency_error(error) is False


class TestRetryOnDeadlock:
    """Tests for retry_on_deadlock function."""

    @pytest.mark.asyncio
    async def test_success_without_retry(self):
        """Should return result immediately on success."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_on_deadlock(session, operation)

        assert result == "success"
        assert call_count == 1
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_retries_on_deadlock(self):
        """Should retry on deadlock and succeed on second attempt."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("deadlock detected")
            return "success after retry"

        result = await retry_on_deadlock(session, operation, base_delay=0.01)

        assert result == "success after retry"
        assert call_count == 2
        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_multiple_times(self):
        """Should retry up to max_attempts times."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("deadlock detected")
            return "success after multiple retries"

        result = await retry_on_deadlock(
            session, operation, max_attempts=3, base_delay=0.01
        )

        assert result == "success after multiple retries"
        assert call_count == 3
        assert session.rollback.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Should raise exception after exhausting all retries."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise Exception("deadlock detected - persistent")

        with pytest.raises(Exception, match="deadlock detected - persistent"):
            await retry_on_deadlock(session, operation, max_attempts=3, base_delay=0.01)

        assert call_count == 3
        assert session.rollback.call_count == 2  # Rollback happens before each retry

    @pytest.mark.asyncio
    async def test_no_retry_on_non_deadlock_error(self):
        """Should not retry on non-deadlock errors."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("some other error")

        with pytest.raises(ValueError, match="some other error"):
            await retry_on_deadlock(session, operation, base_delay=0.01)

        assert call_count == 1
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Should use exponential backoff between retries."""
        session = AsyncMock()
        timestamps = []

        async def operation():
            timestamps.append(asyncio.get_event_loop().time())
            if len(timestamps) < 3:
                raise Exception("deadlock detected")
            return "success"

        await retry_on_deadlock(session, operation, max_attempts=3, base_delay=0.05)

        assert len(timestamps) == 3
        # First retry should wait ~0.05s, second ~0.1s
        # Allow some tolerance for timing
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]
        assert delay1 >= 0.04  # ~0.05 with tolerance
        assert delay2 >= 0.08  # ~0.1 with tolerance
        assert delay2 > delay1  # Exponential growth

    @pytest.mark.asyncio
    async def test_handles_pending_rollback_error(self):
        """Should handle PendingRollbackError from SQLAlchemy."""
        session = AsyncMock()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate the cascading error from a deadlock
                raise Exception(
                    "This Session's transaction has been rolled back due to a "
                    "previous exception during flush. deadlock detected"
                )
            return "recovered"

        result = await retry_on_deadlock(session, operation, base_delay=0.01)

        assert result == "recovered"
        assert call_count == 2
