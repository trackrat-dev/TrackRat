"""
Tests for the disabled-data-source feature flag.

Covers:
- ``Settings.disabled_data_source_set`` / ``Settings.is_data_source_disabled``
  parsing (case-insensitive, whitespace-trimmed, empty -> all enabled).
- ``trackrat.services.departure.active_data_sources`` dropping globally disabled
  sources from both the ``ALL_DATA_SOURCES`` default and explicit requests.
"""

import pytest

from trackrat.config import Settings
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
