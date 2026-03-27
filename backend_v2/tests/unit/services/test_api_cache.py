"""
Comprehensive unit tests for ApiCacheService.

Tests the API response caching system including cache hits/misses,
parameter hashing, expiration, and pre-computation of expensive queries.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import CachedApiResponse
from trackrat.services.api_cache import ApiCacheService


class TestApiCacheService:
    """Test cases for the ApiCacheService class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = Mock()
        return db

    @pytest.fixture
    def cache_service(self):
        """Create an ApiCacheService instance for testing."""
        return ApiCacheService()

    @pytest.fixture
    def sample_response(self):
        """Create a sample API response for testing."""
        return {
            "segments": [
                {"from": "NY", "to": "NP", "congestion": "normal"},
                {"from": "NP", "to": "TR", "congestion": "moderate"},
            ],
            "generated_at": "2025-01-01T12:00:00Z",
        }

    def test_parameter_hashing_consistency(self, cache_service):
        """Test that parameter hashing is consistent regardless of order."""
        params1 = {"time_window_hours": 3, "max_per_segment": 100, "data_source": "NJT"}
        params2 = {"data_source": "NJT", "time_window_hours": 3, "max_per_segment": 100}
        params3 = {"max_per_segment": 100, "data_source": "NJT", "time_window_hours": 3}

        hash1 = cache_service._hash_params(params1)
        hash2 = cache_service._hash_params(params2)
        hash3 = cache_service._hash_params(params3)

        # All should produce the same hash
        assert hash1 == hash2 == hash3

    def test_parameter_hashing_different_values(self, cache_service):
        """Test that different parameter values produce different hashes."""
        params1 = {"time_window_hours": 3, "data_source": "NJT"}
        params2 = {"time_window_hours": 2, "data_source": "NJT"}
        params3 = {"time_window_hours": 3, "data_source": "AMTRAK"}
        params4 = {"time_window_hours": 3}  # Missing data_source

        hash1 = cache_service._hash_params(params1)
        hash2 = cache_service._hash_params(params2)
        hash3 = cache_service._hash_params(params3)
        hash4 = cache_service._hash_params(params4)

        # All should be different
        assert len({hash1, hash2, hash3, hash4}) == 4

    def test_parameter_hashing_handles_special_types(self, cache_service):
        """Test that parameter hashing handles None, dates, and other types."""
        params = {
            "string": "value",
            "integer": 42,
            "float": 3.14,
            "none_value": None,
            "boolean": True,
            "date": datetime(2025, 1, 1, 12, 0, 0),
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        # Should not raise any exceptions
        hash_result = cache_service._hash_params(params)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 produces 64 hex characters

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(
        self, cache_service, mock_db, sample_response
    ):
        """Test that a cache hit returns the cached response."""
        endpoint = "/api/v2/routes/congestion"
        params = {"time_window_hours": 3, "data_source": "NJT"}
        params_hash = cache_service._hash_params(params)

        # Mock a cached response that hasn't expired
        cached_record = Mock(spec=CachedApiResponse)
        cached_record.response = sample_response
        cached_record.generated_at = datetime.now(UTC)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = cached_record
        mock_db.execute.return_value = mock_result

        with patch("trackrat.services.api_cache.now_et") as mock_now:
            mock_now.return_value = datetime.now(UTC)

            result = await cache_service.get_cached_response(mock_db, endpoint, params)

        assert result == sample_response
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service, mock_db):
        """Test that a cache miss returns None."""
        endpoint = "/api/v2/routes/congestion"
        params = {"time_window_hours": 3}

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await cache_service.get_cached_response(mock_db, endpoint, params)

        assert result is None
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_cache_returns_none(self, cache_service, mock_db):
        """Test that expired cache entries are not returned."""
        endpoint = "/api/v2/routes/congestion"
        params = {"time_window_hours": 3}

        # The query should filter out expired entries, so this shouldn't return anything
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("trackrat.services.api_cache.now_et") as mock_now:
            mock_now.return_value = datetime.now(UTC)

            result = await cache_service.get_cached_response(mock_db, endpoint, params)

        assert result is None

    @pytest.mark.asyncio
    async def test_store_cached_response(self, cache_service, mock_db, sample_response):
        """Test storing a response in the cache via upsert."""
        endpoint = "/api/v2/routes/congestion"
        params = {"time_window_hours": 3, "data_source": "NJT"}
        ttl_seconds = 600

        with patch("trackrat.services.api_cache.now_et") as mock_now:
            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_now.return_value = current_time

            await cache_service.store_cached_response(
                mock_db, endpoint, params, sample_response, ttl_seconds
            )

        # Verify upsert statement was executed (single execute for INSERT ... ON CONFLICT)
        assert mock_db.execute.call_count == 1

        # Verify the upsert statement contains correct values
        executed_stmt = mock_db.execute.call_args[0][0]
        # Compiled statement should be a PostgreSQL INSERT with ON CONFLICT
        compiled = executed_stmt.compile(compile_kwargs={"literal_binds": False})
        stmt_str = str(compiled)
        assert "INSERT INTO cached_api_responses" in stmt_str
        assert "ON CONFLICT" in stmt_str

        # db.add should NOT be called (upsert uses execute directly)
        mock_db.add.assert_not_called()

        # Verify commit was called
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_cached_response_replaces_existing(
        self, cache_service, mock_db
    ):
        """Test that storing a response with same key uses upsert (ON CONFLICT DO UPDATE)."""
        endpoint = "/api/v2/routes/congestion"
        params = {"time_window_hours": 3}
        response1 = {"data": "first"}
        response2 = {"data": "second"}

        # Store first response
        await cache_service.store_cached_response(mock_db, endpoint, params, response1)

        # Reset mocks
        mock_db.reset_mock()

        # Store second response with same endpoint and params
        await cache_service.store_cached_response(mock_db, endpoint, params, response2)

        # Verify a single upsert was executed (not separate delete + insert)
        assert mock_db.execute.call_count == 1

        # Verify the statement is an upsert with ON CONFLICT
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = executed_stmt.compile(compile_kwargs={"literal_binds": False})
        stmt_str = str(compiled)
        assert "ON CONFLICT" in stmt_str

        # db.add should NOT be called
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, cache_service, mock_db):
        """Test cleanup of expired cache entries."""
        # Mock the delete execution result
        mock_result = Mock()
        mock_result.rowcount = 5  # Simulate 5 deleted records
        mock_db.execute.return_value = mock_result

        with patch("trackrat.services.api_cache.now_et") as mock_now:
            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_now.return_value = current_time

            deleted_count = await cache_service.cleanup_expired_cache(mock_db)

        assert deleted_count == 5
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache_none_expired(self, cache_service, mock_db):
        """Test cleanup when no cache entries are expired."""
        mock_result = Mock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        deleted_count = await cache_service.cleanup_expired_cache(mock_db)

        assert deleted_count == 0
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_precompute_congestion_responses(self, cache_service, mock_db):
        """Test pre-computation of congestion responses."""
        # Mock the compute method to return a simple response
        mock_response = {
            "aggregated_segments": [],
            "individual_segments": [],
            "train_positions": [],
            "generated_at": "2025-01-01T12:00:00Z",
        }

        with patch.object(
            cache_service, "_compute_congestion_response", return_value=mock_response
        ) as mock_compute:
            with patch.object(cache_service, "store_cached_response") as mock_store:
                await cache_service.precompute_congestion_responses(mock_db)

                # Should compute for 13 default parameter combinations
                assert mock_compute.call_count == 13

                # Should store each computed response
                assert mock_store.call_count == 13

                # Verify the parameter combinations
                expected_params = [
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 0,
                        "data_source": None,
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": None,
                    },
                    {
                        "time_window_hours": 3,
                        "max_per_segment": 100,
                        "data_source": None,
                    },
                    {
                        "time_window_hours": 3,
                        "max_per_segment": 0,
                        "data_source": None,
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 0,
                        "data_source": "NJT",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "NJT",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "PATH",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "AMTRAK",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "LIRR",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "MNR",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "SUBWAY",
                    },
                    {
                        "time_window_hours": 2,
                        "max_per_segment": 100,
                        "data_source": "PATCO",
                    },
                    {
                        "time_window_hours": 3,
                        "max_per_segment": 100,
                        "data_source": "NJT",
                    },
                ]

                for i, expected_param in enumerate(expected_params):
                    actual_params = mock_compute.call_args_list[i][0][1]
                    assert actual_params == expected_param

                    # Verify store was called with correct endpoint and TTL
                    store_call = mock_store.call_args_list[i]
                    assert store_call.kwargs["endpoint"] == "/api/v2/routes/congestion"
                    assert store_call.kwargs["params"] == expected_param
                    assert store_call.kwargs["ttl_seconds"] == 600  # 10 minutes

    @pytest.mark.asyncio
    async def test_precompute_handles_computation_errors(self, cache_service, mock_db):
        """Test that pre-computation continues even if some computations fail."""
        # Make compute fail on first call, succeed on others
        with patch.object(
            cache_service, "_compute_congestion_response"
        ) as mock_compute:
            mock_compute.side_effect = [
                Exception("Computation failed"),
            ] + [{"data": f"response{i}"} for i in range(2, 14)]

            with patch.object(cache_service, "store_cached_response") as mock_store:
                await cache_service.precompute_congestion_responses(mock_db)

                # Should try to compute all 13
                assert mock_compute.call_count == 13

                # Should only store the 12 successful ones
                assert mock_store.call_count == 12

    @pytest.mark.asyncio
    async def test_compute_congestion_response(self, cache_service, mock_db):
        """Test computation of congestion response."""
        params = {"time_window_hours": 3, "max_per_segment": 100, "data_source": "NJT"}

        # Mock the congestion analyzer
        mock_aggregated = [
            Mock(
                from_station="NY",
                to_station="NP",
                data_source="NJT",
                congestion_level="normal",
                congestion_factor=1.05,
                average_delay_minutes=2.5,
                sample_count=10,
                baseline_minutes=15.0,
                avg_transit_minutes=15.5,
                cancellation_count=0,
                cancellation_rate=0.0,
                train_count=10,
                baseline_train_count=12,
                frequency_factor=0.83,
                frequency_level="healthy",
            )
        ]
        mock_individual = []
        mock_journeys = [
            Mock(
                train_id="1234",
                line_code="NE",
                data_source="NJT",
                is_cancelled=False,
                progress=Mock(journey_percent=50),
            )
        ]

        with patch.object(
            cache_service.congestion_analyzer,
            "get_network_congestion_with_trains",
            return_value=(mock_aggregated, mock_journeys, mock_individual),
        ):
            # Mock departure service position calculation
            mock_position = Mock(
                last_departed_station_code="NY",
                at_station_code=None,
                next_station_code="NP",
                between_stations=True,
            )

            with patch.object(
                cache_service.departure_service,
                "_calculate_train_position",
                return_value=mock_position,
            ):
                with patch("trackrat.services.api_cache.now_et") as mock_now:
                    mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

                    with patch(
                        "trackrat.config.stations.get_station_name"
                    ) as mock_station_name:
                        mock_station_name.side_effect = lambda x: f"{x} Station"

                        result = await cache_service._compute_congestion_response(
                            mock_db, params
                        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "aggregated_segments" in result
        assert "individual_segments" in result
        assert "train_positions" in result
        assert "metadata" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["total_trains"] == 1
        assert metadata["congestion_levels"]["normal"] == 1
        assert metadata["congestion_levels"]["moderate"] == 0

    @pytest.mark.asyncio
    async def test_compute_congestion_filters_by_data_source(
        self, cache_service, mock_db
    ):
        """Test that congestion computation filters by data source when specified."""
        params = {"time_window_hours": 3, "max_per_segment": 100, "data_source": "NJT"}

        # Mock data already filtered by data source (SQL layer handles filtering)
        mock_aggregated = [
            Mock(
                from_station="NY",
                to_station="NP",
                data_source="NJT",
                congestion_level="normal",
                congestion_factor=1.0,
                average_delay_minutes=0,
                sample_count=10,
                baseline_minutes=15,
                avg_transit_minutes=15,
                cancellation_count=0,
                cancellation_rate=0,
                train_count=10,
                baseline_train_count=12,
                frequency_factor=0.83,
                frequency_level="healthy",
            ),
        ]
        mock_individual = []
        mock_journeys = [
            Mock(
                train_id="1234",
                line_code="NE",
                data_source="NJT",
                is_cancelled=False,
                progress=None,
            ),
        ]

        with patch.object(
            cache_service.congestion_analyzer,
            "get_network_congestion_with_trains",
            return_value=(mock_aggregated, mock_journeys, mock_individual),
        ) as mock_congestion:
            # Mock position calculations
            with patch.object(
                cache_service.departure_service,
                "_calculate_train_position",
                return_value=Mock(
                    last_departed_station_code="NY",
                    at_station_code=None,
                    next_station_code="NP",
                    between_stations=True,
                ),
            ):
                with patch("trackrat.services.api_cache.now_et") as mock_now:
                    mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

                    with patch(
                        "trackrat.config.stations.get_station_name"
                    ) as mock_station_name:
                        mock_station_name.side_effect = lambda x: f"{x} Station"

                        result = await cache_service._compute_congestion_response(
                            mock_db, params
                        )

        # Verify data_source was passed through to the congestion analyzer
        mock_congestion.assert_called_once_with(mock_db, 3, 100, "NJT")
        # Should only include NJT data
        assert len(result["aggregated_segments"]) == 1
        assert result["aggregated_segments"][0]["data_source"] == "NJT"
        assert len(result["train_positions"]) == 1
        assert result["train_positions"][0]["data_source"] == "NJT"

    @pytest.mark.asyncio
    async def test_compute_congestion_skips_cancelled_trains(
        self, cache_service, mock_db
    ):
        """Test that cancelled trains are excluded from position calculations."""
        params = {"time_window_hours": 3, "max_per_segment": 100, "data_source": None}

        mock_journeys = [
            Mock(
                train_id="1234",
                line_code="NE",
                data_source="NJT",
                is_cancelled=True,
                progress=None,
            ),
            Mock(
                train_id="5678",
                line_code="NE",
                data_source="NJT",
                is_cancelled=False,
                progress=None,
            ),
        ]

        with patch.object(
            cache_service.congestion_analyzer,
            "get_network_congestion_with_trains",
            return_value=([], mock_journeys, []),
        ):
            with patch.object(
                cache_service.departure_service,
                "_calculate_train_position",
                return_value=Mock(
                    last_departed_station_code="NY",
                    at_station_code=None,
                    next_station_code="NP",
                    between_stations=True,
                ),
            ):
                with patch("trackrat.services.api_cache.now_et") as mock_now:
                    mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

                    result = await cache_service._compute_congestion_response(
                        mock_db, params
                    )

        # Should only include the non-cancelled train
        assert len(result["train_positions"]) == 1
        assert result["train_positions"][0]["train_id"] == "5678"

    @pytest.mark.asyncio
    async def test_precompute_departure_responses(self, cache_service, mock_db):
        """Test pre-computation of departure responses."""
        mock_response = {
            "departures": [
                {
                    "train_id": "1234",
                    "line": {
                        "code": "NE",
                        "name": "Northeast Corridor",
                        "color": "#000000",
                    },
                    "destination": "Trenton",
                }
            ],
            "metadata": {
                "from_station": {"code": "NY", "name": "New York Penn Station"}
            },
        }

        with patch.object(
            cache_service, "_compute_departure_response", return_value=mock_response
        ) as mock_compute:
            with patch.object(cache_service, "store_cached_response") as mock_store:
                await cache_service.precompute_departure_responses(mock_db)

                # 22 routes × 2 hide_departed variants = 44 calls
                # (8 with destination + 6 origin-only + 8 subway terminals)
                assert mock_compute.call_count == 44

                assert mock_store.call_count == 44

                # Verify first few routes have correct structure including data_sources key
                first_call_params = mock_compute.call_args_list[0][0][1]
                assert first_call_params == {
                    "from_station": "NY",
                    "to_station": "TR",
                    "date": None,
                    "limit": 50,
                    "hide_departed": False,
                    "data_sources": None,
                }

                # Verify all calls include the data_sources key
                for i in range(44):
                    actual_params = mock_compute.call_args_list[i][0][1]
                    assert (
                        "data_sources" in actual_params
                    ), f"Call {i} missing data_sources key: {actual_params}"

                    store_call = mock_store.call_args_list[i]
                    assert store_call.kwargs["endpoint"] == "/api/v2/trains/departures"
                    assert store_call.kwargs["ttl_seconds"] == 120

    @pytest.mark.asyncio
    async def test_precompute_departure_handles_errors(self, cache_service, mock_db):
        """Test that departure pre-computation continues even if some computations fail."""
        with patch.object(cache_service, "_compute_departure_response") as mock_compute:
            # 44 calls: first fails, rest succeed
            # (22 routes × 2 hide_departed variants = 44)
            mock_compute.side_effect = [
                Exception("Computation failed"),
            ] + [{"departures": []}] * 43

            with patch.object(cache_service, "store_cached_response") as mock_store:
                await cache_service.precompute_departure_responses(mock_db)

                # 22 routes × 2 hide_departed variants = 44 calls
                assert mock_compute.call_count == 44

                # Only 43 successful (first one failed)
                assert mock_store.call_count == 43

    @pytest.mark.asyncio
    async def test_compute_departure_response(self, cache_service, mock_db):
        """Test computation of departure response."""
        params = {"from_station": "NY", "to_station": "TR", "limit": 50}

        mock_departure_response = Mock()
        mock_departure_response.model_dump.return_value = {
            "departures": [
                {
                    "train_id": "1234",
                    "line": {
                        "code": "NE",
                        "name": "Northeast Corridor",
                        "color": "#000000",
                    },
                    "destination": "Trenton",
                }
            ],
            "metadata": {
                "from_station": {"code": "NY", "name": "New York Penn Station"},
                "to_station": {"code": "TR", "name": "Trenton"},
                "count": 1,
            },
        }

        with patch.object(
            cache_service.departure_service,
            "get_departures",
            return_value=mock_departure_response,
        ):
            result = await cache_service._compute_departure_response(mock_db, params)

        assert isinstance(result, dict)
        assert "departures" in result
        assert "metadata" in result
        assert len(result["departures"]) == 1
        assert result["departures"][0]["train_id"] == "1234"

    @pytest.mark.asyncio
    async def test_compute_departure_response_with_none_destination(
        self, cache_service, mock_db
    ):
        """Test departure computation with no destination (all departures from station)."""
        params = {"from_station": "NY", "to_station": None, "limit": 50}

        mock_departure_response = Mock()
        mock_departure_response.model_dump.return_value = {
            "departures": [
                {"train_id": "1234", "destination": "Trenton"},
                {"train_id": "5678", "destination": "Princeton Junction"},
            ],
            "metadata": {
                "from_station": {"code": "NY", "name": "New York Penn Station"},
                "to_station": None,
                "count": 2,
            },
        }

        with patch.object(
            cache_service.departure_service,
            "get_departures",
            return_value=mock_departure_response,
        ):
            result = await cache_service._compute_departure_response(mock_db, params)

        assert len(result["departures"]) == 2
        assert result["metadata"]["to_station"] is None


class TestApiCacheIntegration:
    """Integration tests for cache service with other components."""

    @pytest.mark.asyncio
    async def test_cache_service_with_real_hash_function(self):
        """Test the actual hash function produces valid SHA256 hashes."""
        service = ApiCacheService()

        # Test various parameter types
        test_cases = [
            {"simple": "value"},
            {"number": 123, "string": "test", "none": None},
            {"nested": {"key": "value"}, "list": [1, 2, 3]},
            {},  # Empty params
        ]

        hashes = set()
        for params in test_cases:
            hash_result = service._hash_params(params)

            # Should be a valid SHA256 hash (64 hex chars)
            assert len(hash_result) == 64
            assert all(c in "0123456789abcdef" for c in hash_result)

            hashes.add(hash_result)

        # All hashes should be unique
        assert len(hashes) == len(test_cases)

    @pytest.mark.asyncio
    async def test_cache_ttl_boundary_conditions(self):
        """Test cache behavior at TTL boundaries."""
        service = ApiCacheService()
        mock_db = AsyncMock(spec=AsyncSession)

        # Test with exactly expired cache (should not return)
        current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        cached_record = Mock(spec=CachedApiResponse)
        cached_record.response = {"data": "test"}
        cached_record.generated_at = current_time - timedelta(seconds=120)
        cached_record.expires_at = current_time  # Exactly at expiration

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None  # Query filters it out
        mock_db.execute.return_value = mock_result

        with patch("trackrat.services.api_cache.now_et") as mock_now:
            mock_now.return_value = current_time

            result = await service.get_cached_response(
                mock_db, "/api/test", {"param": "value"}
            )

        assert result is None  # Should not return expired cache
