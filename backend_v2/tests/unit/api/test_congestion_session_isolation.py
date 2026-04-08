"""
Tests for multi-provider congestion cache miss session isolation.

Verifies the fix for poisoned DB session when a provider query times out
in the multi-provider congestion loop. Each provider must get its own
session via get_session() so a timeout in one doesn't corrupt the session
for subsequent providers or the final merge.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_multi_provider_uses_isolated_sessions(client):
    """Each provider in the multi-provider cache miss loop must receive
    its own session from get_session(), not the request's db session.

    This prevents a timeout in one provider from poisoning the session
    used by subsequent providers.
    """
    sessions_created = []

    def _make_mock_session():
        """Create a uniquely identifiable mock session."""
        session = AsyncMock()
        sessions_created.append(session)
        return session

    captured_db_args = []
    call_count = 0

    async def _capture_provider_call(db, data_source, *args, **kwargs):
        """Record which session each provider call receives."""
        nonlocal call_count
        call_count += 1
        captured_db_args.append((data_source, db))

    # Mock cache miss for multi-provider path
    mock_cache = MagicMock()
    mock_cache.get_cached_response = AsyncMock(return_value=None)
    mock_cache.merge_congestion_from_provider_caches = AsyncMock(return_value=None)

    # Track get_session() calls — each should yield a fresh session
    def _mock_get_session():
        mock_session = _make_mock_session()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with (
        patch("trackrat.api.routes.ApiCacheService", return_value=mock_cache),
        patch(
            "trackrat.api.routes._compute_and_cache_single_provider",
            side_effect=_capture_provider_call,
        ),
        patch("trackrat.api.routes.get_session", side_effect=_mock_get_session),
    ):
        response = client.get("/api/v2/routes/congestion?systems=NJT,PATH")

    # Two providers + one merge = three get_session() calls
    assert len(sessions_created) == 3, (
        f"Expected 3 get_session() calls (2 providers + 1 merge), "
        f"got {len(sessions_created)}"
    )

    # Each provider call should receive a distinct session
    assert (
        len(captured_db_args) == 2
    ), f"Expected 2 provider calls (NJT, PATH), got {len(captured_db_args)}"
    njt_session = captured_db_args[0][1]
    path_session = captured_db_args[1][1]
    assert (
        njt_session is not path_session
    ), "Each provider must receive its own isolated session"

    # Merge should also use a fresh session, not the request db
    merge_db = mock_cache.merge_congestion_from_provider_caches.call_args[0][0]
    assert (
        merge_db is sessions_created[2]
    ), "Merge must use a fresh session from get_session(), not the request db"


@pytest.mark.asyncio
async def test_multi_provider_timeout_skips_provider_continues(client):
    """When one provider times out, the loop should skip it and continue
    to the next provider using a fresh session.
    """

    class FakeQueryCanceled(Exception):
        """Simulates asyncpg.exceptions.QueryCanceledError."""

        pass

    call_order = []

    async def _provider_with_njt_timeout(db, data_source, *args, **kwargs):
        """NJT times out, PATH succeeds."""
        call_order.append(data_source)
        if data_source == "NJT":
            raise FakeQueryCanceled("statement timeout")

    mock_cache = MagicMock()
    mock_cache.get_cached_response = AsyncMock(return_value=None)
    # First call is the cache lookup (must miss), second is post-computation merge
    mock_cache.merge_congestion_from_provider_caches = AsyncMock(
        side_effect=[None, {"segments": [], "train_positions": []}]
    )

    def _mock_get_session():
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with (
        patch("trackrat.api.routes.ApiCacheService", return_value=mock_cache),
        patch(
            "trackrat.api.routes._compute_and_cache_single_provider",
            side_effect=_provider_with_njt_timeout,
        ),
        patch("trackrat.api.routes.get_session", side_effect=_mock_get_session),
    ):
        response = client.get("/api/v2/routes/congestion?systems=NJT,PATH")

    # Both providers should be attempted (NJT fails, PATH succeeds)
    assert call_order == [
        "NJT",
        "PATH",
    ], f"Expected both providers to be attempted in order, got {call_order}"

    # Merge should still be called to combine available results
    assert (
        mock_cache.merge_congestion_from_provider_caches.called
    ), "Merge should be called even when one provider times out"

    # Should return 200 (partial results from PATH), not 500
    assert response.status_code == 200, (
        f"Expected 200 (partial results), got {response.status_code}: "
        f"{response.text}"
    )
