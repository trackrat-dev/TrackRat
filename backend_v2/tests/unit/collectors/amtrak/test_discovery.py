"""
Unit tests for AmtrakDiscoveryCollector.

Tests train discovery logic, NYP filtering, and result formatting.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.models.api import AmtrakTrainData
from tests.fixtures.amtrak_api_responses import (
    AMTRAK_FULL_RESPONSE,
    EXPECTED_NYP_TRAIN_IDS,
    EXPECTED_MULTI_HUB_TRAIN_IDS,
)
from tests.factories.amtrak import (
    create_amtrak_train_data,
    create_mock_amtrak_api_response,
)


class TestAmtrakDiscoveryCollector:
    """Test suite for AmtrakDiscoveryCollector."""

    @pytest.fixture
    def collector(self):
        """Create an AmtrakDiscoveryCollector instance for testing."""
        return AmtrakDiscoveryCollector()

    @pytest.fixture
    def mock_client(self):
        """Create a mock AmtrakClient."""
        mock_client = AsyncMock()
        return mock_client

    def _parse_response_to_objects(self, raw_response):
        """Helper to convert raw dict response to AmtrakTrainData objects."""
        parsed_response = {}
        for train_num, train_list in raw_response.items():
            parsed_response[train_num] = [
                AmtrakTrainData(**train_dict) for train_dict in train_list
            ]
        return parsed_response

    async def test_discover_trains_with_nyp_stops(self, collector, mock_client):
        """Test discovering trains that stop at discovery hubs (including NYP)."""
        parsed_response = self._parse_response_to_objects(AMTRAK_FULL_RESPONSE)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should discover trains that serve any discovery hub (NYP, PHL, WAS, BOS, WIL)
        assert isinstance(result, list)
        assert len(result) == len(EXPECTED_MULTI_HUB_TRAIN_IDS)
        assert set(result) == set(EXPECTED_MULTI_HUB_TRAIN_IDS)

    async def test_discover_trains_filtering_non_hub(self, collector, mock_client):
        """Test that trains not serving discovery hubs are included if they serve hubs."""
        # Create response with mix of hub and non-hub trains
        raw_response = create_mock_amtrak_api_response(
            train_count=2,
            include_non_nyp_train=True,  # 2 hub trains + 1 train serving PHL
        )
        parsed_response = self._parse_response_to_objects(raw_response)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should return all trains that serve discovery hubs (including 350-5 which serves PHL)
        assert len(result) == 3
        # Should include the PHL train (350-5) since PHL is now a discovery hub
        assert "350-5" in result

    async def test_discover_trains_empty_response(self, collector, mock_client):
        """Test handling of empty API response."""
        mock_client.get_all_trains.return_value = {}
        collector.client = mock_client

        result = await collector.discover_trains()

        assert result == []

    async def test_discover_trains_no_hub_trains(self, collector, mock_client):
        """Test when trains serve PHL (which is now a discovery hub)."""
        # Create response with only trains serving discovery hubs (like PHL)
        raw_response = create_mock_amtrak_api_response(
            train_count=0,
            include_non_nyp_train=True,  # This creates train 350-5 serving PHL
        )
        parsed_response = self._parse_response_to_objects(raw_response)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should discover the train serving PHL (350-5) since PHL is now a discovery hub
        assert result == ["350-5"]

    async def test_discover_trains_api_error(self, collector, mock_client, caplog):
        """Test handling of API errors."""
        mock_client.get_all_trains.side_effect = Exception("API Error")
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should return empty list on error
        assert result == []
        # Should log the error
        assert "amtrak_discovery_failed" in caplog.text
        assert "API Error" in caplog.text

    def test_stops_at_nyp_true(self, collector):
        """Test _stops_at_nyp method returns True for trains serving NYP."""
        train = create_amtrak_train_data(stops_at_nyp=True)
        result = collector._stops_at_nyp(train)
        assert result is True

    def test_stops_at_nyp_false(self, collector):
        """Test _stops_at_nyp method returns False for trains not serving NYP."""
        train = create_amtrak_train_data(stops_at_nyp=False)
        result = collector._stops_at_nyp(train)
        assert result is False

    def test_stops_at_nyp_empty_stations(self, collector):
        """Test _stops_at_nyp method with train having no stations."""
        train = create_amtrak_train_data(stations=[])
        result = collector._stops_at_nyp(train)
        assert result is False

    async def test_run_method_interface(self, collector, mock_client):
        """Test the run method interface."""
        parsed_response = self._parse_response_to_objects(AMTRAK_FULL_RESPONSE)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        result = await collector.run()

        # Should return expected result structure
        assert isinstance(result, dict)
        assert "discovered_trains" in result
        assert "train_ids" in result
        assert "data_source" in result
        assert result["data_source"] == "AMTRAK"
        assert result["discovered_trains"] == len(EXPECTED_MULTI_HUB_TRAIN_IDS)
        assert set(result["train_ids"]) == set(EXPECTED_MULTI_HUB_TRAIN_IDS)

    async def test_logging_discovery_results(self, collector, mock_client, caplog):
        """Test that discovery results are logged."""
        parsed_response = self._parse_response_to_objects(AMTRAK_FULL_RESPONSE)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        await collector.discover_trains()

        # Should log discovery completion with count
        assert "amtrak_discovery_complete" in caplog.text
        assert f"discovered_count={len(EXPECTED_MULTI_HUB_TRAIN_IDS)}" in caplog.text

    async def test_logging_discovered_trains(self, collector, mock_client, caplog):
        """Test that individual discovered trains are logged."""
        # Set log level to DEBUG to capture debug messages
        import logging

        caplog.set_level(logging.DEBUG)

        parsed_response = self._parse_response_to_objects(AMTRAK_FULL_RESPONSE)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        await collector.discover_trains()

        # Should log each discovered train (debug level)
        assert "discovered_amtrak_train" in caplog.text
        # Should include train details
        assert "train_id=2150-5" in caplog.text
        assert "route=Acela" in caplog.text

    async def test_unique_train_ids(self, collector, mock_client):
        """Test that duplicate train IDs are handled correctly."""
        # Create response with duplicate trains - already as objects
        duplicate_response = {
            "2150": [
                create_amtrak_train_data(train_num="2150", train_id="2150-5"),
                create_amtrak_train_data(
                    train_num="2150", train_id="2150-5"
                ),  # Duplicate
            ]
        }
        mock_client.get_all_trains.return_value = duplicate_response
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should include duplicates if they're in the data (API responsibility)
        # This tests that our code doesn't modify the API response structure
        assert len(result) == 2
        assert result[0] == result[1] == "2150-5"

    async def test_mixed_train_types(self, collector, mock_client):
        """Test discovery with different train types (Acela, Regional, etc.)."""
        mixed_response = {
            "2150": [
                create_amtrak_train_data(
                    train_num="2150", route="Acela", stops_at_nyp=True
                )
            ],
            "141": [
                create_amtrak_train_data(
                    train_num="141", route="Northeast Regional", stops_at_nyp=True
                )
            ],
            "280": [
                create_amtrak_train_data(
                    train_num="280", route="Empire Service", stops_at_nyp=True
                )
            ],
        }
        mock_client.get_all_trains.return_value = mixed_response
        collector.client = mock_client

        result = await collector.discover_trains()

        # Should discover all train types that serve NYP
        assert len(result) == 3
        assert "2150-5" in result
        assert "141-5" in result
        assert "280-5" in result

    async def test_client_context_manager_usage(self, collector, mock_client):
        """Test that the run method uses client context manager."""
        parsed_response = self._parse_response_to_objects(AMTRAK_FULL_RESPONSE)
        mock_client.get_all_trains.return_value = parsed_response
        collector.client = mock_client

        # Mock the context manager
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        result = await collector.run()

        # Should have used the context manager
        mock_client.__aenter__.assert_called_once()
        mock_client.__aexit__.assert_called_once()

        # Should have correct result
        assert result["discovered_trains"] > 0
