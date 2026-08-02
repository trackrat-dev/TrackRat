"""Test NJT client handling of None/null responses."""

import pytest
from unittest.mock import AsyncMock

from trackrat.collectors.njt.client import (
    NJTransitClient,
    NJTransitNullDataError,
    TrainNotFoundError,
    _has_explicit_null_train_fields,
)


def test_null_train_data_requires_present_fields():
    """An error envelope or changed schema must not look like known null data."""
    assert _has_explicit_null_train_fields(
        {
            "TRAIN_ID": None,
            "LINECODE": None,
            "BACKCOLOR": None,
            "DESTINATION": None,
        }
    )
    assert not _has_explicit_null_train_fields({"error": "authentication failed"})
    assert not _has_explicit_null_train_fields(
        {"TRAIN_ID": None, "LINECODE": None, "BACKCOLOR": None}
    )


@pytest.mark.asyncio
async def test_get_train_stop_list_all_fields_none_raises_null_data_error():
    """Test that all-fields-null raises NJTransitNullDataError (NOT TrainNotFoundError).

    This is the key behavior change: when the NJT API returns a response with all
    key fields null, NJT simply has no detail for that train — it is not a genuine
    "train not found". The departure board (getTrainSchedule) often still shows
    these trains. Using a distinct exception prevents the 3-strike expiry from
    triggering.

    The message must NOT call this transient (issue #1725). It reads as an
    invitation to retry, and production evidence says a retry cannot help: the
    same train numbers return null every night, and individual trains return
    null 113-162 times in a single day.
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

    message = str(exc_info.value)
    assert "3840" in message, f"message must name the train, got: {message!r}"
    assert (
        "null data" in message.lower()
    ), f"message must say what happened upstream, got: {message!r}"
    assert "transient" not in message.lower(), (
        "the null-data condition is persistent, not transient — a message "
        f"claiming otherwise invites a retry that cannot help: {message!r}"
    )


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
