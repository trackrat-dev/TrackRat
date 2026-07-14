"""
Tests for the disabled-data-source feature flag.

Covers:
- ``Settings.disabled_data_source_set`` / ``Settings.is_data_source_disabled``
  parsing (case-insensitive, whitespace-trimmed, empty -> all enabled).
- ``trackrat.services.departure.active_data_sources`` dropping globally disabled
  sources from both the ``ALL_DATA_SOURCES`` default and explicit requests,
  including the ``CONGESTION_PROVIDERS`` list used by the congestion precompute
  and merge paths.
- ``trackrat.api.utils.ensure_source_enabled`` raising 404 for the train_id /
  source-scoped endpoints (train detail, history, predictions, route history).
"""

import pytest
from fastapi import HTTPException

from trackrat.api.utils import ensure_source_enabled
from trackrat.config import Settings
from trackrat.services.api_cache import CONGESTION_PROVIDERS
from trackrat.services.departure import ALL_DATA_SOURCES, active_data_sources
from trackrat.settings import get_settings


def _make_settings(disabled: str) -> Settings:
    """Build a Settings with only the disabled-sources field varied."""
    return Settings(
        database_url="postgresql://user:pass@localhost/db",
        njt_api_token="token",
        disabled_data_sources=disabled,
    )


def test_disabled_set_empty_string_means_all_enabled():
    """An empty flag disables nothing: empty set, every source enabled."""
    settings = _make_settings("")
    assert settings.disabled_data_source_set == set()
    for source in ALL_DATA_SOURCES:
        assert (
            settings.is_data_source_disabled(source) is False
        ), f"{source} should be enabled when flag is empty"


def test_disabled_set_parses_case_and_whitespace():
    """Values are uppercased and trimmed; internal spaces/casing tolerated."""
    settings = _make_settings("bart, WMATA ,mbta")
    assert settings.disabled_data_source_set == {"BART", "WMATA", "MBTA"}


def test_is_data_source_disabled_is_case_insensitive():
    """is_data_source_disabled matches regardless of caller casing."""
    settings = _make_settings("bart, WMATA ,mbta")
    # Disabled sources report True for any casing of the input.
    assert settings.is_data_source_disabled("bart") is True
    assert settings.is_data_source_disabled("BART") is True
    assert settings.is_data_source_disabled("Wmata") is True
    assert settings.is_data_source_disabled("MBTA") is True
    # A source not in the flag stays enabled.
    assert settings.is_data_source_disabled("NJT") is False
    assert settings.is_data_source_disabled("njt") is False


def test_disabled_set_ignores_empty_fragments():
    """Stray commas/whitespace produce no empty-string members."""
    settings = _make_settings(" , BART ,, ")
    assert settings.disabled_data_source_set == {"BART"}


@pytest.fixture
def clear_settings_cache():
    """Ensure get_settings() re-reads env before and after the test.

    get_settings is @lru_cache'd, so the env var only takes effect once the
    cache is cleared; we also clear afterward so a stale disabled-sources
    Settings can't leak into other tests.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_active_data_sources_nothing_disabled(monkeypatch, clear_settings_cache):
    """With no flag set, active_data_sources is a pass-through."""
    monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "")
    get_settings.cache_clear()

    # Default (None) resolves to the full ordered list, unchanged.
    assert active_data_sources(None) == ALL_DATA_SOURCES
    # An explicit request is echoed back verbatim.
    assert active_data_sources(["NJT", "AMTRAK"]) == ["NJT", "AMTRAK"]


def test_active_data_sources_drops_disabled(monkeypatch, clear_settings_cache):
    """Disabled sources are removed from both the default and explicit lists."""
    monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART,WMATA")
    get_settings.cache_clear()

    # Default list drops the two disabled sources, preserving order/others.
    expected_default = [s for s in ALL_DATA_SOURCES if s not in {"BART", "WMATA"}]
    assert active_data_sources(None) == expected_default
    assert "BART" not in active_data_sources(None)
    assert "WMATA" not in active_data_sources(None)

    # Explicit request with a disabled source drops only the disabled one.
    assert active_data_sources(["NJT", "BART"]) == ["NJT"]


def test_active_data_sources_filters_congestion_providers(
    monkeypatch, clear_settings_cache
):
    """The congestion precompute/merge providers list drops disabled sources.

    The scheduler precompute iterates ``active_data_sources(CONGESTION_PROVIDERS)``
    and the /routes/congestion merge default uses the same resolution, so a
    disabled source must never appear in the effective provider set — otherwise
    its congestion cache would be (re)built and merged into the all-systems map.
    """
    monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART,WMATA,MBTA,METRA")
    get_settings.cache_clear()

    effective = active_data_sources(CONGESTION_PROVIDERS)

    for disabled in ("BART", "WMATA", "MBTA", "METRA"):
        assert disabled not in effective, f"{disabled} must be dropped"
    # Enabled congestion providers survive, order preserved.
    assert effective == [
        p for p in CONGESTION_PROVIDERS if p not in {"BART", "WMATA", "MBTA", "METRA"}
    ]
    assert "NJT" in effective and "PATH" in effective


class TestEnsureSourceEnabled:
    """ensure_source_enabled guards train_id/source-scoped endpoints with 404."""

    def test_raises_404_for_disabled_source(self, monkeypatch, clear_settings_cache):
        """A disabled source raises HTTPException(404) — the record must not be served."""
        monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART")
        get_settings.cache_clear()

        with pytest.raises(HTTPException) as exc_info:
            ensure_source_enabled("BART")
        assert exc_info.value.status_code == 404
        assert "BART" in exc_info.value.detail

    def test_case_insensitive_disabled_match(self, monkeypatch, clear_settings_cache):
        """The guard matches regardless of caller casing (mirrors is_data_source_disabled)."""
        monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART")
        get_settings.cache_clear()

        with pytest.raises(HTTPException):
            ensure_source_enabled("bart")

    def test_noop_for_enabled_source(self, monkeypatch, clear_settings_cache):
        """An enabled source is a no-op (no exception)."""
        monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART")
        get_settings.cache_clear()

        # Should not raise.
        ensure_source_enabled("NJT")

    def test_noop_for_none(self, monkeypatch, clear_settings_cache):
        """A None data_source is a no-op: nothing to reject when unscoped."""
        monkeypatch.setenv("TRACKRAT_DISABLED_DATA_SOURCES", "BART")
        get_settings.cache_clear()

        # Should not raise.
        ensure_source_enabled(None)


class TestComposePassthrough:
    """Guard the deployment plumbing, not just the Python logic (issue #1484).

    The startup script writes TRACKRAT_DISABLED_DATA_SOURCES into the compose
    project's .env file, but a compose .env only interpolates ${VAR} references
    in docker-compose.yml — it does NOT inject env into containers. Unless the
    api service's environment block explicitly passes the variable through, the
    container never sees it and every "disabled" collector silently runs. That
    exact gap shipped with the feature (2a1d231) and went unnoticed in
    production for months because the only signal was the *absence* of a log
    line. This test fails if the passthrough is ever dropped again.
    """

    def test_api_service_passes_disabled_sources_through(self):
        from pathlib import Path

        compose = Path(__file__).parents[2] / "docker-compose.yml"
        assert compose.exists(), f"expected compose file at {compose}"
        content = compose.read_text()

        assert (
            "TRACKRAT_DISABLED_DATA_SOURCES: ${TRACKRAT_DISABLED_DATA_SOURCES"
            in content
        ), (
            "backend_v2/docker-compose.yml must pass TRACKRAT_DISABLED_DATA_SOURCES "
            "through to the api container (environment block). Without it the "
            "instance-level flag never reaches Settings and disabled-source "
            "collectors run anyway — see issue #1484."
        )
