"""
Tests for get_session() BaseException handling in db/engine.py.

Verifies that CancelledError and other BaseException subclasses
trigger an explicit rollback before propagating, preventing
idle-in-transaction connection leaks.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from trackrat.db.engine import get_session


class TestGetSessionBaseExceptionHandling:
    """Verify get_session() rolls back on BaseException subclasses."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def mock_sessionmaker(self, mock_session):
        """Create a mock sessionmaker that yields our mock session."""
        sm = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        sm.return_value = ctx
        return sm

    @pytest.mark.asyncio
    async def test_cancelled_error_triggers_rollback(
        self, mock_session, mock_sessionmaker
    ):
        """CancelledError inside get_session must trigger explicit rollback."""
        with patch("trackrat.db.engine.get_sessionmaker", return_value=mock_sessionmaker):
            with pytest.raises(asyncio.CancelledError):
                async with get_session() as session:
                    raise asyncio.CancelledError()

        mock_session.rollback.assert_called()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called()

    @pytest.mark.asyncio
    async def test_regular_exception_triggers_rollback(
        self, mock_session, mock_sessionmaker
    ):
        """Regular Exception inside get_session triggers rollback (existing behavior)."""
        with patch("trackrat.db.engine.get_sessionmaker", return_value=mock_sessionmaker):
            with pytest.raises(ValueError):
                async with get_session() as session:
                    raise ValueError("test error")

        mock_session.rollback.assert_called()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called()

    @pytest.mark.asyncio
    async def test_successful_session_commits(self, mock_session, mock_sessionmaker):
        """Successful session usage commits and closes."""
        with patch("trackrat.db.engine.get_sessionmaker", return_value=mock_sessionmaker):
            async with get_session() as session:
                pass  # No error

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called()

    @pytest.mark.asyncio
    async def test_rollback_failure_during_cancellation_still_propagates(
        self, mock_session, mock_sessionmaker
    ):
        """If rollback fails during CancelledError, the error still propagates."""
        mock_session.rollback.side_effect = RuntimeError("connection lost")

        with patch("trackrat.db.engine.get_sessionmaker", return_value=mock_sessionmaker):
            with pytest.raises(asyncio.CancelledError):
                async with get_session() as session:
                    raise asyncio.CancelledError()

        # Rollback was attempted even though it failed
        mock_session.rollback.assert_called()
        mock_session.close.assert_called()
