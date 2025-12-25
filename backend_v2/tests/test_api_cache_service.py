"""
Tests for API cache service.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from trackrat.models.database import CachedApiResponse
from trackrat.services.api_cache import ApiCacheService
from trackrat.utils.time import now_et


@pytest.mark.asyncio
async def test_cache_params_hash_consistency():
    """Test that identical params produce identical hashes."""
    service = ApiCacheService()

    params1 = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}
    params2 = {"date": None, "limit": 50, "to_station": "TR", "from_station": "NY"}

    hash1 = service._hash_params(params1)
    hash2 = service._hash_params(params2)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_cache_params_hash_different():
    """Test that different params produce different hashes."""
    service = ApiCacheService()

    params1 = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}
    params2 = {"from_station": "NY", "to_station": "NP", "date": None, "limit": 50}

    hash1 = service._hash_params(params1)
    hash2 = service._hash_params(params2)

    assert hash1 != hash2


@pytest.mark.asyncio
async def test_cache_params_hash_missing_date_key():
    """Test that missing 'date' key produces different hash than date=None."""
    service = ApiCacheService()

    params_with_date = {
        "from_station": "NY",
        "to_station": "TR",
        "date": None,
        "limit": 50,
    }
    params_without_date = {"from_station": "NY", "to_station": "TR", "limit": 50}

    hash_with = service._hash_params(params_with_date)
    hash_without = service._hash_params(params_without_date)

    assert hash_with != hash_without


@pytest.mark.asyncio
async def test_get_cached_response_hit(db_session):
    """Test cache hit returns stored response."""
    service = ApiCacheService()

    params = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}
    response_data = {"departures": [], "metadata": {"count": 0}}

    await service.store_cached_response(
        db=db_session,
        endpoint="/api/v2/trains/departures",
        params=params,
        response=response_data,
        ttl_seconds=120,
    )

    cached = await service.get_cached_response(
        db=db_session, endpoint="/api/v2/trains/departures", params=params
    )

    assert cached is not None
    assert cached["departures"] == []
    assert cached["metadata"]["count"] == 0


@pytest.mark.asyncio
async def test_get_cached_response_miss(db_session):
    """Test cache miss returns None."""
    service = ApiCacheService()

    params = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}

    cached = await service.get_cached_response(
        db=db_session, endpoint="/api/v2/trains/departures", params=params
    )

    assert cached is None


@pytest.mark.asyncio
async def test_get_cached_response_expired(db_session):
    """Test expired cache entry returns None."""
    service = ApiCacheService()

    params = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}
    response_data = {"departures": [], "metadata": {"count": 0}}

    params_hash = service._hash_params(params)
    expired_time = now_et() - timedelta(seconds=200)

    expired_cache = CachedApiResponse(
        endpoint="/api/v2/trains/departures",
        params_hash=params_hash,
        params=params,
        response=response_data,
        generated_at=expired_time,
        expires_at=expired_time + timedelta(seconds=120),
    )

    db_session.add(expired_cache)
    await db_session.commit()

    cached = await service.get_cached_response(
        db=db_session, endpoint="/api/v2/trains/departures", params=params
    )

    assert cached is None


@pytest.mark.asyncio
async def test_precompute_departure_responses(db_session):
    """Test pre-computation creates cache entries for popular routes."""
    service = ApiCacheService()

    with patch.object(service.departure_service, "get_departures") as mock_get:
        from trackrat.models.api import DeparturesResponse

        mock_response = DeparturesResponse(
            departures=[],
            metadata={
                "from_station": {"code": "NY", "name": "New York Penn Station"},
                "to_station": None,
                "date": None,
                "count": 0,
            },
        )
        mock_get.return_value = mock_response

        await service.precompute_departure_responses(db_session)

        assert mock_get.call_count >= 8

        expected_params = {
            "from_station": "NY",
            "to_station": "TR",
            "date": None,
            "limit": 50,
        }
        cached = await service.get_cached_response(
            db=db_session, endpoint="/api/v2/trains/departures", params=expected_params
        )

        assert cached is not None


@pytest.mark.asyncio
async def test_cleanup_expired_cache(db_session):
    """Test cleanup removes expired entries."""
    service = ApiCacheService()

    params = {"from_station": "NY", "to_station": "TR", "date": None, "limit": 50}
    params_hash = service._hash_params(params)
    expired_time = now_et() - timedelta(seconds=200)

    expired_cache = CachedApiResponse(
        endpoint="/api/v2/trains/departures",
        params_hash=params_hash,
        params=params,
        response={"departures": []},
        generated_at=expired_time,
        expires_at=expired_time + timedelta(seconds=120),
    )

    db_session.add(expired_cache)
    await db_session.commit()

    deleted_count = await service.cleanup_expired_cache(db_session)

    assert deleted_count == 1

    cached = await service.get_cached_response(
        db=db_session, endpoint="/api/v2/trains/departures", params=params
    )
    assert cached is None


@pytest.mark.asyncio
async def test_compute_departure_response_params():
    """Test that _compute_departure_response uses correct params."""
    service = ApiCacheService()

    with patch.object(service.departure_service, "get_departures") as mock_get:
        mock_response = AsyncMock()
        mock_response.model_dump.return_value = {"departures": [], "metadata": {}}
        mock_get.return_value = mock_response

        mock_db = AsyncMock()
        params = {"from_station": "NY", "to_station": "TR", "limit": 50}

        await service._compute_departure_response(mock_db, params)

        mock_get.assert_called_once_with(
            db=mock_db,
            from_station="NY",
            to_station="TR",
            date=None,
            time_from=None,
            time_to=None,
            limit=50,
            skip_individual_refresh=True,  # Critical: skip during precompute
        )


@pytest.mark.asyncio
async def test_compute_departure_response_skips_individual_refresh():
    """Test that cache precomputation skips individual train refreshes.

    This test verifies the fix for excessive API calls during cache precomputation.
    The precompute job should pass skip_individual_refresh=True to avoid making
    individual getTrainStopList API calls for each stale train.
    """
    service = ApiCacheService()

    with patch.object(service.departure_service, "get_departures") as mock_get:
        mock_response = AsyncMock()
        mock_response.model_dump.return_value = {"departures": [], "metadata": {}}
        mock_get.return_value = mock_response

        mock_db = AsyncMock()
        params = {"from_station": "NY", "to_station": "TR", "limit": 50}

        await service._compute_departure_response(mock_db, params)

        # Verify skip_individual_refresh=True was passed
        call_kwargs = mock_get.call_args.kwargs
        assert "skip_individual_refresh" in call_kwargs
        assert call_kwargs["skip_individual_refresh"] is True
