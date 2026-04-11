"""
Unit tests for WMATA collector client initialization.

Tests _ensure_client() which lazily initializes the WMATA API client
from settings. This fixes the bug where JIT refresh created WMATACollector()
without a client, then called collect_journey_details() directly (bypassing
run()), hitting an AssertionError on the bare assert.

See: https://github.com/trackrat-dev/trackrat/issues/899
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trackrat.collectors.wmata.collector import WMATACollector
from trackrat.collectors.wmata.client import WMATAClient

_SETTINGS_PATH = "trackrat.settings.get_settings"


class TestEnsureClient:
    """Tests for WMATACollector._ensure_client()."""

    def test_ensure_client_already_set(self):
        """When a client is already provided, _ensure_client returns True immediately."""
        client = MagicMock(spec=WMATAClient)
        collector = WMATACollector(client=client)

        assert collector._ensure_client() is True
        assert collector.client is client
        # Should NOT have called get_settings since client was already set
        assert collector._owns_client is False

    @patch(_SETTINGS_PATH)
    def test_ensure_client_creates_from_settings(self, mock_get_settings):
        """When no client provided, _ensure_client creates one from settings."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = "test-api-key-123"
        mock_get_settings.return_value = mock_settings

        collector = WMATACollector()
        assert collector.client is None

        result = collector._ensure_client()

        assert result is True
        assert collector.client is not None
        assert isinstance(collector.client, WMATAClient)
        assert collector._owns_client is True

    @patch(_SETTINGS_PATH)
    def test_ensure_client_no_api_key(self, mock_get_settings):
        """When no API key is configured, _ensure_client returns False."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = ""
        mock_get_settings.return_value = mock_settings

        collector = WMATACollector()

        result = collector._ensure_client()

        assert result is False
        assert collector.client is None

    @patch(_SETTINGS_PATH)
    def test_ensure_client_idempotent(self, mock_get_settings):
        """Calling _ensure_client twice doesn't create a second client."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = "test-key"
        mock_get_settings.return_value = mock_settings

        collector = WMATACollector()
        collector._ensure_client()
        first_client = collector.client

        # Call again — should reuse existing client
        result = collector._ensure_client()

        assert result is True
        assert collector.client is first_client
        # get_settings only called once (first call)
        mock_get_settings.assert_called_once()


class TestCollectJourneyDetailsClientInit:
    """Tests that collect_journey_details properly initializes the client."""

    @pytest.mark.asyncio
    @patch(_SETTINGS_PATH)
    async def test_collect_journey_details_no_api_key_returns_gracefully(
        self, mock_get_settings
    ):
        """collect_journey_details returns without error when no API key configured."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = ""
        mock_get_settings.return_value = mock_settings

        collector = WMATACollector()
        session = AsyncMock()
        journey = MagicMock()
        journey.train_id = "WMATA_RD_A15_20260405T120000"

        # Should NOT raise AssertionError — this was the original bug
        await collector.collect_journey_details(session, journey)

        # Session should not have been touched
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    @patch("trackrat.collectors.wmata.collector.with_train_lock")
    @patch(_SETTINGS_PATH)
    async def test_collect_journey_details_initializes_client(
        self, mock_get_settings, mock_with_train_lock
    ):
        """collect_journey_details initializes client from settings when needed."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = "test-key"
        mock_get_settings.return_value = mock_settings

        # Make with_train_lock just call the function directly
        async def fake_lock(train_id, date, func, *args):
            await func(*args)

        mock_with_train_lock.side_effect = fake_lock

        collector = WMATACollector()
        assert collector.client is None

        session = AsyncMock()
        journey = MagicMock()
        journey.train_id = "WMATA_RD_A15_20260405T120000"
        journey.journey_date = "2026-04-05"

        # Patch the inner method to avoid needing real API calls
        collector._collect_journey_details_locked = AsyncMock()

        await collector.collect_journey_details(session, journey)

        # Client should now be initialized
        assert collector.client is not None
        assert isinstance(collector.client, WMATAClient)
        # Inner method should have been called
        collector._collect_journey_details_locked.assert_called_once_with(
            session, journey
        )


class TestRunUsesEnsureClient:
    """Tests that run() uses _ensure_client instead of inline init."""

    @pytest.mark.asyncio
    @patch(_SETTINGS_PATH)
    async def test_run_no_api_key(self, mock_get_settings):
        """run() returns error dict when no API key configured."""
        mock_settings = MagicMock()
        mock_settings.wmata_api_key = ""
        mock_get_settings.return_value = mock_settings

        collector = WMATACollector()
        result = await collector.run()

        assert result["data_source"] == "WMATA"
        assert result["error"] == "no API key"
        assert result["arrivals_fetched"] == 0
