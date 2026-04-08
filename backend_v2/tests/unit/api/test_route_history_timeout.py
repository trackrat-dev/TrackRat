"""
Tests for route history endpoint timeout behavior.

Verifies the fix for issue #903: route history query timeout leaves DB session
in broken state, causing BART/MBTA 500s. The fix uses a dedicated session with
asyncio.wait_for(timeout=45.0) to ensure clean cancellation before the 60s
command_timeout fires.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_route_history_timeout_returns_504(client):
    """When compute_route_history exceeds the 45s timeout, return HTTP 504.

    The @handle_errors decorator catches TimeoutError and returns 504.
    This verifies the timeout wrapper fires and propagates correctly,
    instead of letting the 60s command_timeout fire and corrupt the session.
    """

    async def _slow_computation(*args, **kwargs):
        """Simulate a route history query that takes too long (BART/MBTA)."""
        await asyncio.sleep(3600)

    # Mock cache miss so we reach compute_route_history
    mock_cache = MagicMock()
    mock_cache.get_cached_response = AsyncMock(return_value=None)

    with (
        patch("trackrat.api.routes.ApiCacheService", return_value=mock_cache),
        patch(
            "trackrat.api.routes.compute_route_history", side_effect=_slow_computation
        ),
    ):
        # Patch asyncio.wait_for in routes module to use a short timeout for testing
        original_wait_for = asyncio.wait_for

        async def fast_wait_for(coro, *, timeout):
            return await original_wait_for(coro, timeout=0.1)

        with patch("trackrat.api.routes.asyncio.wait_for", side_effect=fast_wait_for):
            response = client.get(
                "/api/v2/routes/history?from_station=NY&to_station=TR&data_source=NJT"
            )

    # Should get 504 (timeout) — NOT 500 (session corruption)
    assert response.status_code == 504, (
        f"Expected 504 (clean timeout via handle_errors), "
        f"got {response.status_code}: {response.json()}"
    )


@pytest.mark.asyncio
async def test_route_history_uses_dedicated_session(client):
    """Verify that compute_route_history receives a session from get_session(),
    not the request's main db session from Depends(get_db).

    This isolation prevents transaction corruption from leaking to the
    request's main session when a query is cancelled mid-execution.
    """
    session_from_get_session = AsyncMock()
    captured_db_arg = []

    async def _capture_db_arg(db, *args, **kwargs):
        """Record which session object is passed to compute_route_history."""
        captured_db_arg.append(db)
        # Raise to short-circuit — we only care about the session identity
        raise ValueError("captured")

    mock_cache = MagicMock()
    mock_cache.get_cached_response = AsyncMock(return_value=None)

    # Mock get_session to return a known sentinel session
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session_from_get_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("trackrat.api.routes.ApiCacheService", return_value=mock_cache),
        patch("trackrat.api.routes.compute_route_history", side_effect=_capture_db_arg),
        patch("trackrat.api.routes.get_session", return_value=mock_ctx),
    ):
        response = client.get(
            "/api/v2/routes/history?from_station=NY&to_station=TR&data_source=NJT"
        )

    # The endpoint will return 500 because compute_route_history raised ValueError,
    # but we only care that the right session was passed
    assert (
        len(captured_db_arg) == 1
    ), "compute_route_history should have been called once"
    assert captured_db_arg[0] is session_from_get_session, (
        "compute_route_history should receive the dedicated session from get_session(), "
        "not the request's main db session"
    )
