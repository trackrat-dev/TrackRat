"""
Comprehensive unit tests for TrainValidationService.

Tests the end-to-end validation service that ensures trains from transit APIs
are properly accessible through our API endpoints.
"""

import time
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, Mock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import ValidationResult as ValidationResultDB
from trackrat.services.validation import TrainValidationService, ValidationResult
from trackrat.settings import Settings


class TestValidationResult:
    """Test cases for ValidationResult class."""

    def test_validation_result_calculates_coverage_correctly(self):
        """Test that coverage percentage is calculated correctly."""
        timestamp = datetime.now(UTC)

        # Test with some matching trains
        result = ValidationResult(
            route="NY->TR",
            source="NJT",
            transit_trains={"1234", "5678", "9012"},
            api_trains={"1234", "5678", "3456"},
            timestamp=timestamp,
        )

        # 2 out of 3 transit trains found = 66.67%
        assert result.coverage_percent == pytest.approx(66.67, rel=0.01)
        assert result.missing_trains == {"9012"}
        assert result.extra_trains == {"3456"}

    def test_validation_result_perfect_coverage(self):
        """Test 100% coverage when all transit trains are found."""
        timestamp = datetime.now(UTC)

        result = ValidationResult(
            route="NY->NP",
            source="NJT",
            transit_trains={"1234", "5678"},
            api_trains={"1234", "5678", "9012"},  # Has extra trains
            timestamp=timestamp,
        )

        assert result.coverage_percent == 100.0
        assert result.missing_trains == set()
        assert result.extra_trains == {"9012"}

    def test_validation_result_zero_coverage(self):
        """Test 0% coverage when no transit trains are found."""
        timestamp = datetime.now(UTC)

        result = ValidationResult(
            route="NY->TR",
            source="NJT",
            transit_trains={"1234", "5678"},
            api_trains={"9012", "3456"},
            timestamp=timestamp,
        )

        assert result.coverage_percent == 0.0
        assert result.missing_trains == {"1234", "5678"}
        assert result.extra_trains == {"9012", "3456"}

    def test_validation_result_empty_transit_trains(self):
        """Test coverage when no transit trains exist."""
        timestamp = datetime.now(UTC)

        result = ValidationResult(
            route="NY->TR",
            source="NJT",
            transit_trains=set(),
            api_trains={"1234"},
            timestamp=timestamp,
        )

        assert result.coverage_percent == 100.0  # No trains to find = 100%
        assert result.missing_trains == set()
        assert result.extra_trains == {"1234"}


class TestTrainValidationService:
    """Test cases for TrainValidationService class."""

    @pytest.fixture
    def test_settings(self):
        """Create test settings."""
        return Settings(
            njt_api_token="test_token",
            internal_api_url="http://localhost:8000",
            validation_max_trains_to_verify=5,
            environment="testing",
        )

    @pytest.fixture
    def validation_service(self, test_settings):
        """Create a ValidationService instance for testing."""
        return TrainValidationService(settings=test_settings)

    @pytest.fixture
    def mock_njt_client(self):
        """Create a mock NJ Transit client."""
        client = AsyncMock()
        client.get_train_schedule_with_stops = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_amtrak_client(self):
        """Create a mock Amtrak client."""
        client = AsyncMock()
        client.get_all_trains = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock()
        client.aclose = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_context_manager_initializes_clients(self, validation_service):
        """Test that context manager properly initializes and closes clients."""
        with patch("trackrat.services.validation.NJTransitClient") as MockNJT:
            with patch("trackrat.services.validation.AmtrakClient") as MockAmtrak:
                with patch(
                    "trackrat.services.validation.httpx.AsyncClient"
                ) as MockHTTP:
                    mock_njt = AsyncMock()
                    mock_amtrak = AsyncMock()
                    mock_http = AsyncMock()

                    MockNJT.return_value = mock_njt
                    MockAmtrak.return_value = mock_amtrak
                    MockHTTP.return_value = mock_http

                    async with validation_service:
                        assert validation_service.njt_client == mock_njt
                        assert validation_service.amtrak_client == mock_amtrak
                        assert validation_service.http_client == mock_http

                    # Verify clients were closed
                    mock_njt.close.assert_called_once()
                    mock_amtrak.close.assert_called_once()
                    mock_http.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_njt_trains_for_route(self, validation_service, mock_njt_client):
        """Test getting NJ Transit trains for a specific route."""
        validation_service.njt_client = mock_njt_client

        # Mock NJT API response
        mock_njt_client.get_train_schedule_with_stops.return_value = {
            "ITEMS": [
                {
                    "TRAIN_ID": "1234",
                    "STOPS": [
                        {"STATION_2CHAR": "NY"},
                        {"STATION_2CHAR": "NP"},
                        {"STATION_2CHAR": "TR"},
                    ],
                },
                {
                    "TRAIN_ID": "5678",
                    "STOPS": [
                        {"STATION_2CHAR": "NY"},
                        {"STATION_2CHAR": "NP"},
                    ],
                },
                {
                    "TRAIN_ID": "9012",
                    "STOPS": [
                        {"STATION_2CHAR": "NY"},
                        {"STATION_2CHAR": "TR"},
                    ],
                },
            ]
        }

        trains = await validation_service.get_njt_trains_for_route("NY", "TR")

        assert trains == {"1234", "9012"}  # Only trains that go from NY to TR
        mock_njt_client.get_train_schedule_with_stops.assert_called_once_with("NY")

    @pytest.mark.asyncio
    async def test_get_njt_trains_handles_errors(
        self, validation_service, mock_njt_client
    ):
        """Test that NJT train fetching handles errors gracefully."""
        validation_service.njt_client = mock_njt_client
        mock_njt_client.get_train_schedule_with_stops.side_effect = Exception(
            "API Error"
        )

        trains = await validation_service.get_njt_trains_for_route("NY", "TR")

        assert trains == set()  # Returns empty set on error

    @pytest.mark.asyncio
    async def test_get_amtrak_trains_for_route(
        self, validation_service, mock_amtrak_client
    ):
        """Test getting Amtrak trains for a specific route."""
        validation_service.amtrak_client = mock_amtrak_client

        # Mock Amtrak API response with trains
        mock_train1 = Mock()
        mock_train1.trainID = "123-2025-01-01"
        mock_train1.stations = [
            Mock(code="NYP"),  # NY Penn in Amtrak codes
            Mock(code="PJC"),  # Princeton Junction
        ]

        mock_train2 = Mock()
        mock_train2.trainID = "456-2025-01-01"
        mock_train2.stations = [
            Mock(code="PJC"),  # Wrong direction
            Mock(code="NYP"),
        ]

        mock_train3 = Mock()
        mock_train3.trainID = "789-2025-01-01"
        mock_train3.stations = [
            Mock(code="NYP"),
            Mock(code="WIL"),  # Wilmington
        ]

        mock_amtrak_client.get_all_trains.return_value = {
            "NYP": [mock_train1, mock_train2, mock_train3],
        }

        with patch(
            "trackrat.services.validation.INTERNAL_TO_AMTRAK_STATION_MAP"
        ) as mock_map:
            mock_map.get.side_effect = lambda x, default: {
                "NY": "NYP",
                "PJ": "PJC",
            }.get(x, default)

            trains = await validation_service.get_amtrak_trains_for_route("NY", "PJ")

        # Should include trains going both directions NY<->PJ, prefixed with "A"
        assert trains == {"A123", "A456"}

    @pytest.mark.asyncio
    async def test_get_amtrak_trains_maps_station_codes(
        self, validation_service, mock_amtrak_client
    ):
        """Test that Amtrak station codes are properly mapped."""
        validation_service.amtrak_client = mock_amtrak_client

        mock_train = Mock()
        mock_train.trainID = "100"
        mock_train.stations = [
            Mock(code="NYP"),
            Mock(code="WIL"),
        ]

        mock_amtrak_client.get_all_trains.return_value = {"NYP": [mock_train]}

        with patch(
            "trackrat.services.validation.INTERNAL_TO_AMTRAK_STATION_MAP"
        ) as mock_map:
            # Map NY->NYP and WI->WIL
            mock_map.get.side_effect = lambda x, default: {
                "NY": "NYP",
                "WI": "WIL",
            }.get(x, default)

            trains = await validation_service.get_amtrak_trains_for_route("NY", "WI")

        assert trains == {"A100"}

    @pytest.mark.asyncio
    async def test_get_trains_from_our_api(self, validation_service, mock_http_client):
        """Test getting trains from our API endpoint."""
        validation_service.http_client = mock_http_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "departures": [
                {"train_id": "1234"},
                {"train_id": "5678"},
                {"train_id": "A123"},
            ]
        }
        mock_http_client.get.return_value = mock_response

        trains = await validation_service.get_trains_from_our_api("NY", "TR")

        assert trains == {"1234", "5678", "A123"}
        mock_http_client.get.assert_called_once_with(
            "http://localhost:8000/api/v2/trains/departures",
            params={"from": "NY", "to": "TR", "limit": 100},
        )

    @pytest.mark.asyncio
    async def test_get_trains_from_our_api_handles_errors(
        self, validation_service, mock_http_client
    ):
        """Test that API train fetching handles errors gracefully."""
        validation_service.http_client = mock_http_client

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_http_client.get.return_value = mock_response

        trains = await validation_service.get_trains_from_our_api("NY", "TR")

        assert trains == set()

    @pytest.mark.asyncio
    async def test_verify_train_details_accessible(
        self, validation_service, mock_http_client
    ):
        """Test verifying if train details are accessible."""
        validation_service.http_client = mock_http_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "train_id": "1234",
            "status": "OnTime",
            "stops": [{"station": "NY"}, {"station": "TR"}],
        }
        mock_http_client.get.return_value = mock_response

        with patch("trackrat.services.validation.now_et") as mock_now:
            mock_now.return_value.date.return_value.isoformat.return_value = (
                "2025-01-01"
            )

            result = await validation_service.verify_train_details_accessible("1234")

        assert result["accessible"] is True
        assert result["has_stops"] is True
        assert result["stop_count"] == 2
        assert result["status"] == "OnTime"

    @pytest.mark.asyncio
    async def test_verify_train_details_not_accessible(
        self, validation_service, mock_http_client
    ):
        """Test verifying train details when not accessible."""
        validation_service.http_client = mock_http_client

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Train not found"
        mock_http_client.get.return_value = mock_response

        result = await validation_service.verify_train_details_accessible("9999")

        assert result["accessible"] is False
        assert result["status_code"] == 404
        assert "Train not found" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_route(self, validation_service, mock_http_client):
        """Test validating a single route for multiple sources."""
        validation_service.http_client = mock_http_client

        # Mock API trains
        api_response = Mock()
        api_response.status_code = 200
        api_response.json.return_value = {
            "departures": [
                {"train_id": "1234"},
                {"train_id": "5678"},
            ]
        }
        mock_http_client.get.return_value = api_response

        with patch.object(validation_service, "get_njt_trains_for_route") as mock_njt:
            with patch.object(
                validation_service, "get_amtrak_trains_for_route"
            ) as mock_amtrak:
                mock_njt.return_value = {"1234", "5678", "9012"}
                mock_amtrak.return_value = {"A123", "A456"}

                with patch.object(validation_service, "_save_validation_result"):
                    with patch.object(
                        validation_service, "verify_train_details_accessible"
                    ) as mock_verify:
                        mock_verify.return_value = {"accessible": False}

                        results = await validation_service.validate_route(
                            "NY", "TR", ["NJT", "AMTRAK"]
                        )

        assert len(results) == 2

        # Check NJT result
        njt_result = results[0]
        assert njt_result.route == "NY->TR"
        assert njt_result.source == "NJT"
        assert njt_result.missing_trains == {"9012"}
        assert njt_result.coverage_percent == pytest.approx(66.67, rel=0.01)

        # Check Amtrak result
        amtrak_result = results[1]
        assert amtrak_result.source == "AMTRAK"
        assert amtrak_result.missing_trains == {"A123", "A456"}
        assert amtrak_result.coverage_percent == 0.0

    @pytest.mark.asyncio
    async def test_save_validation_result(self, validation_service):
        """Test saving validation results to database."""
        timestamp = datetime.now(UTC)
        result = ValidationResult(
            route="NY->TR",
            source="NJT",
            transit_trains={"1234", "5678"},
            api_trains={"1234"},
            timestamp=timestamp,
        )
        missing_details = {"5678": {"accessible": False, "error": "Not found"}}

        with patch("trackrat.services.validation.get_session") as mock_get_session:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_db

            await validation_service._save_validation_result(result, missing_details)

            # Verify record was added
            mock_db.add.assert_called_once()
            added_record = mock_db.add.call_args[0][0]
            assert isinstance(added_record, ValidationResultDB)
            assert added_record.route == "NY->TR"
            assert added_record.source == "NJT"
            assert added_record.transit_train_count == 2
            assert added_record.api_train_count == 1
            assert added_record.coverage_percent == pytest.approx(50.0, rel=0.01)
            assert added_record.missing_trains == ["5678"]
            assert added_record.details["missing_train_details"] == missing_details

            # Note: commit is handled by get_session() context manager, not explicitly

    @pytest.mark.asyncio
    async def test_save_validation_result_handles_errors(self, validation_service):
        """Test that save validation handles database errors gracefully."""
        result = ValidationResult(
            route="NY->TR",
            source="NJT",
            transit_trains={"1234"},
            api_trains={"1234"},
            timestamp=datetime.now(UTC),
        )

        with patch("trackrat.services.validation.get_session") as mock_get_session:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.add.side_effect = Exception("Database error")
            mock_get_session.return_value.__aenter__.return_value = mock_db

            # Should not raise, just log error
            await validation_service._save_validation_result(result)

    @pytest.mark.asyncio
    async def test_run_validation_all_routes(self, validation_service):
        """Test running validation for all monitored routes."""
        with patch.object(validation_service, "validate_route") as mock_validate:
            mock_results = [
                ValidationResult(
                    route="NY->WI",
                    source="AMTRAK",
                    transit_trains={"A123"},
                    api_trains={"A123"},
                    timestamp=datetime.now(UTC),
                ),
                ValidationResult(
                    route="NY->PJ",
                    source="NJT",
                    transit_trains={"1234", "5678"},
                    api_trains={"1234"},
                    timestamp=datetime.now(UTC),
                ),
            ]

            # Return different results for different routes
            mock_validate.side_effect = [
                [mock_results[0]],  # NY->WI AMTRAK
                [mock_results[1]],  # NY->PJ NJT/AMTRAK
                [],  # MP->NY
                [],  # NY->HL
            ]

            results = await validation_service.run_validation()

        assert len(results) == 2
        assert mock_validate.call_count == 4  # All monitored routes

    @pytest.mark.asyncio
    async def test_run_validation_handles_route_errors(self, validation_service):
        """Test that validation continues even if some routes fail."""
        with patch.object(validation_service, "validate_route") as mock_validate:
            # First route fails, others succeed
            mock_validate.side_effect = [
                Exception("Route failed"),
                [],
                [],
                [],
            ]

            results = await validation_service.run_validation()

        # Should still process other routes
        assert mock_validate.call_count == 4
        assert len(results) == 0  # No results from failed route

    def test_monitored_routes_configuration(self, validation_service):
        """Test that monitored routes are properly configured."""
        routes = validation_service.MONITORED_ROUTES

        assert len(routes) > 0

        for from_station, to_station, sources in routes:
            assert isinstance(from_station, str)
            assert isinstance(to_station, str)
            assert isinstance(sources, list)
            assert all(s in ["NJT", "AMTRAK"] for s in sources)


class TestValidationMetrics:
    """Test cases for validation metrics recording."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_validation(self):
        """Test that validation metrics are properly recorded."""
        settings = Settings(
            njt_api_token="test",
            internal_api_url="http://localhost:8000",
            validation_max_trains_to_verify=2,
        )
        service = TrainValidationService(settings)

        with patch.object(service, "get_trains_from_our_api", return_value={"1234"}):
            with patch.object(
                service, "get_njt_trains_for_route", return_value={"1234", "5678"}
            ):
                with patch.object(service, "_save_validation_result"):
                    with patch(
                        "trackrat.services.validation.train_validation_coverage"
                    ) as mock_coverage:
                        with patch(
                            "trackrat.services.validation.missing_trains_detected"
                        ) as mock_missing:
                            with patch(
                                "trackrat.services.validation.train_validation_duration"
                            ) as mock_duration:
                                results = await service.validate_route(
                                    "NY", "TR", ["NJT"]
                                )

                                # Verify metrics were recorded
                                mock_coverage.labels.assert_called_with(
                                    route="NY->TR", source="NJT"
                                )
                                mock_coverage.labels().observe.assert_called_once()

                                mock_missing.labels.assert_called_with(
                                    route="NY->TR", source="NJT"
                                )
                                mock_missing.labels().inc.assert_called_with(
                                    1
                                )  # One missing train

                                mock_duration.labels.assert_called_with(
                                    route="NY->TR", source="NJT"
                                )
                                mock_duration.labels().observe.assert_called_once()
