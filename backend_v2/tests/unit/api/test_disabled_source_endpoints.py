"""
API-level tests that endpoints reject / exclude globally-disabled data sources.

These exercise only the guard paths that short-circuit *before* any database
access, so they run without a live Postgres:
- ``/routes/history`` returns 404 for a disabled ``data_source`` (guard fires
  right after source validation, before ``compute_route_history``).
- ``/routes/congestion`` returns an empty map when every requested system is
  disabled (the endpoint normalizes ``requested_systems`` to the active set and
  early-returns before the cache/DB paths).

The row-level exclusion for the analytics queries (a disabled feed's residual
journeys dropped from congestion/summary/segment results) is covered by the
DB-backed integration tests, since it needs seeded rows to be meaningful.
"""

import pytest

from trackrat.settings import get_settings


@pytest.fixture
def disable_bart(monkeypatch):
    """Disable BART for the duration of a test, restoring the settings cache after.

    ``ensure_source_enabled`` / ``active_data_sources`` read the lru-cached
    ``get_settings()`` directly (not via FastAPI ``Depends``), so we set the env
    var and clear the cache here; the request-time call then sees BART disabled.
    """
    monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestDisabledSourceEndpointGuards:
    """Endpoints must not serve data for a source in TRACKRAT_DISABLED_DATA_SOURCES."""

    def test_route_history_rejects_disabled_source(self, client, disable_bart):
        """/routes/history?data_source=BART -> 404, before touching the database."""
        resp = client.get(
            "/api/v2/routes/history",
            params={"from_station": "NY", "to_station": "TR", "data_source": "BART"},
        )
        assert resp.status_code == 404, resp.text
        assert "BART" in resp.json()["detail"]

    def test_route_history_allows_enabled_source_past_guard(self, client, disable_bart):
        """A different (enabled) source is NOT rejected by the disabled-source guard.

        NJT is enabled, so the guard passes; the request proceeds past it (the
        exact downstream status depends on data, but it must never be the
        guard's 404-for-BART). This proves the guard is source-specific.
        """
        resp = client.get(
            "/api/v2/routes/history",
            params={"from_station": "NY", "to_station": "TR", "data_source": "NJT"},
        )
        # Whatever happens downstream, it must not be a 404 naming NJT unavailable.
        if resp.status_code == 404:
            assert "NJT" not in resp.json().get("detail", "")

    def test_congestion_only_disabled_system_returns_empty(self, client, disable_bart):
        """/routes/congestion?systems=BART -> empty map (no disabled trains served)."""
        resp = client.get("/api/v2/routes/congestion", params={"systems": "BART"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["train_positions"] == []
        assert body["aggregated_segments"] == []
        assert body["metadata"]["total_trains"] == 0

    def test_congestion_legacy_disabled_data_source_returns_empty(
        self, client, disable_bart
    ):
        """The legacy ?data_source=BART param is normalized the same way -> empty."""
        resp = client.get("/api/v2/routes/congestion", params={"data_source": "BART"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["train_positions"] == []
