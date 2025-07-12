"""Test NJT client handling of None/null responses."""

import pytest
from unittest.mock import AsyncMock

from trackrat.collectors.njt.client import NJTransitClient, TrainNotFoundError


@pytest.mark.asyncio
async def test_get_train_stop_list_all_fields_none():
    """Test handling when API returns dict with all None values."""
    client = NJTransitClient()

    # Mock response with all fields None (what we're seeing in the logs)
    mock_response = {
        "TRAIN_ID": None,
        "LINECODE": None,
        "BACKCOLOR": None,
        "FORECOLOR": None,
        "SHADOWCOLOR": None,
        "DESTINATION": None,
        "TRANSFERAT": None,
        "STOPS": None,
    }

    client._make_request = AsyncMock(return_value=mock_response)

    # This should raise TrainNotFoundError, not validation error
    with pytest.raises(TrainNotFoundError) as exc_info:
        async with client:
            await client.get_train_stop_list("3840")

    assert "Train 3840 not found - API returned null data" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_train_stop_list_partial_none_fields():
    """Test handling when API returns dict with some None values."""
    client = NJTransitClient()

    # Mock response with partial None values
    mock_response = {
        "TRAIN_ID": "3840",
        "LINECODE": None,  # Some fields are None
        "BACKCOLOR": None,
        "FORECOLOR": None,
        "SHADOWCOLOR": None,
        "DESTINATION": "Trenton",
        "TRANSFERAT": "",
        "STOPS": [],
    }

    client._make_request = AsyncMock(return_value=mock_response)

    # This should still raise validation error since required fields are None
    with pytest.raises(Exception) as exc_info:
        async with client:
            await client.get_train_stop_list("3840")

    # Should get a validation error, not TrainNotFoundError
    assert "Invalid train data format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_train_stop_list_empty_dict():
    """Test handling when API returns empty dict."""
    client = NJTransitClient()

    client._make_request = AsyncMock(return_value={})

    with pytest.raises(TrainNotFoundError) as exc_info:
        async with client:
            await client.get_train_stop_list("3840")

    assert "Train 3840 not found - API returned empty response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_train_stop_list_none_response():
    """Test handling when API returns None."""
    client = NJTransitClient()

    client._make_request = AsyncMock(return_value=None)

    with pytest.raises(TrainNotFoundError) as exc_info:
        async with client:
            await client.get_train_stop_list("3840")

    assert "Train 3840 not found - API returned None" in str(exc_info.value)
