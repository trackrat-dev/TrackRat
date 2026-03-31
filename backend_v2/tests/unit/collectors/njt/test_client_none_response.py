"""Test NJT client handling of None/null responses."""

import pytest
from unittest.mock import AsyncMock

from trackrat.collectors.njt.client import (
    NJTransitClient,
    NJTransitNullDataError,
    TrainNotFoundError,
)


@pytest.mark.asyncio
async def test_get_train_stop_list_all_fields_none_raises_null_data_error():
    """Test that all-fields-null raises NJTransitNullDataError (NOT TrainNotFoundError).

    This is the key behavior change: when the NJT API returns a response with all
    key fields null, it's a transient API issue, not a genuine "train not found".
    The departure board (getTrainSchedule) often still shows these trains.
    Using a distinct exception prevents the 3-strike expiry from triggering.
    """
    client = NJTransitClient()

    # Mock response with all fields None (what we're seeing in production logs)
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

    # Must raise NJTransitNullDataError, NOT TrainNotFoundError
    with pytest.raises(NJTransitNullDataError) as exc_info:
        async with client:
            await client.get_train_stop_list("3840")

    assert "transient" in str(exc_info.value).lower()
    assert "3840" in str(exc_info.value)


@pytest.mark.asyncio
async def test_all_fields_none_is_not_train_not_found():
    """Verify NJTransitNullDataError is NOT a subclass of TrainNotFoundError.

    This is critical: code that catches TrainNotFoundError to increment
    api_error_count must NOT catch NJTransitNullDataError.
    """
    assert not issubclass(NJTransitNullDataError, TrainNotFoundError)


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
