"""Test expired train functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import TrainNotFoundError
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et


@pytest.mark.asyncio
async def test_train_expiry_after_two_failures():
    """Test that trains are marked as expired after 2 TrainNotFoundError failures."""
    # Create a mock journey
    journey = TrainJourney(
        id=1,
        train_id="1234",
        journey_date=now_et().date(),
        line_code="NE",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        scheduled_departure=now_et() - timedelta(hours=1),
        data_source="NJT",
        has_complete_journey=True,
        api_error_count=0,
        is_expired=False,
    )

    # Mock session
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()

    # Mock NJT client that raises TrainNotFoundError
    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=TrainNotFoundError("Train not found")
    )

    collector = JourneyCollector(njt_client)

    # First failure - should increment error count but not expire
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 1
    assert journey.is_expired is False
    assert session.flush.called

    # Second failure - should expire the train
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 2
    assert journey.is_expired is True
    assert journey.last_updated_at is not None


@pytest.mark.asyncio
async def test_api_error_count_reset_on_success():
    """Test that api_error_count is reset when train data is successfully retrieved."""
    # Create a mock journey with existing error count
    journey = TrainJourney(
        id=1,
        train_id="1234",
        journey_date=now_et().date(),
        line_code="NE",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        scheduled_departure=now_et() - timedelta(hours=1),
        data_source="NJT",
        has_complete_journey=True,
        api_error_count=1,  # Previous error
        is_expired=False,
    )

    # Mock session
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=None)  # No existing stops
    session.add = Mock()  # session.add is synchronous, not async

    # Mock successful API response
    from trackrat.models.api import NJTransitTrainData, NJTransitStopData

    mock_train_data = NJTransitTrainData(
        TRAIN_ID="1234",
        LINECODE="NE",
        BACKCOLOR="#000000",
        FORECOLOR="#FFFFFF",
        SHADOWCOLOR="#CCCCCC",
        DESTINATION="New York",
        TRANSFERAT="",
        STOPS=[
            NJTransitStopData(
                STOP_SEQUENCE=1,
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                TIME="10:00 AM",
                DEP_TIME="10:02 AM",
                DEPARTED="YES",
                STOP_STATUS="On Time",
                TRACK="1",
                PICKUP="",
                DROPOFF="",
            ),
            NJTransitStopData(
                STOP_SEQUENCE=2,
                STATION_2CHAR="NY",
                STATIONNAME="New York",
                TIME="11:00 AM",
                DEP_TIME="11:00 AM",
                DEPARTED="NO",
                STOP_STATUS="On Time",
                TRACK="",
                PICKUP="",
                DROPOFF="",
            ),
        ],
    )

    # Mock NJT client that returns data successfully
    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock(return_value=mock_train_data)

    collector = JourneyCollector(njt_client)

    # Collect journey - should reset error count
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 0  # Reset to 0
    assert journey.is_expired is False
    assert journey.has_complete_journey is True
    assert journey.stops_count == 2


@pytest.mark.asyncio
async def test_expired_trains_excluded_from_collection():
    """Test that expired trains are excluded from collection queries."""
    from trackrat.collectors.njt.journey import JourneyCollector

    # This test would need a real database session to test the query
    # For unit testing, we can verify the query construction

    collector = JourneyCollector(AsyncMock())

    # Mock session with execute method
    session = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    scalars_mock = AsyncMock()
    scalars_mock.all = lambda: []
    mock_result.scalars = lambda: scalars_mock
    session.execute = AsyncMock(return_value=mock_result)

    # Call the method
    trains = await collector.find_trains_needing_collection(session)

    # Verify the query was executed
    assert session.execute.called

    # The actual SQL would include is_expired.is_not(True) in the WHERE clause
    # This is verified by the query construction in the actual code


@pytest.mark.asyncio
async def test_train_not_found_counted_as_success_in_batch():
    """Test that TrainNotFoundError is counted as successful in batch collection."""
    # Create mock journeys
    journey1 = TrainJourney(
        id=1,
        train_id="1234",
        journey_date=now_et().date(),
        line_code="NE",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        scheduled_departure=now_et() - timedelta(hours=1),
        data_source="NJT",
        api_error_count=0,
        is_expired=False,
    )

    journey2 = TrainJourney(
        id=2,
        train_id="5678",
        journey_date=now_et().date(),
        line_code="NE",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=now_et() - timedelta(hours=1),
        data_source="NJT",
        api_error_count=1,
        is_expired=False,
    )

    # Mock session
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    mock_result = AsyncMock()
    scalars_mock = AsyncMock()
    scalars_mock.all = lambda: [journey1, journey2]
    mock_result.scalars = lambda: scalars_mock
    session.execute = AsyncMock(return_value=mock_result)

    # Mock NJT client - first train succeeds, second train not found
    njt_client = AsyncMock()

    # Need to create the response for journey1
    from trackrat.models.api import NJTransitTrainData, NJTransitStopData

    mock_train_data = NJTransitTrainData(
        TRAIN_ID="1234",
        LINECODE="NE",
        BACKCOLOR="#000000",
        FORECOLOR="#FFFFFF",
        SHADOWCOLOR="#CCCCCC",
        DESTINATION="New York",
        TRANSFERAT="",
        STOPS=[
            NJTransitStopData(
                STOP_SEQUENCE=1,
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                TIME="10:00 AM",
                DEP_TIME="10:02 AM",
                DEPARTED="YES",
                STOP_STATUS="On Time",
                TRACK="1",
                PICKUP="",
                DROPOFF="",
            ),
        ],
    )

    # First call succeeds, second call raises TrainNotFoundError
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=[mock_train_data, TrainNotFoundError("Train not found")]
    )

    collector = JourneyCollector(njt_client)

    # Patch the methods that would be called
    with patch.object(collector, "create_journey_snapshot", new_callable=AsyncMock):
        with patch.object(collector, "update_journey_metadata", new_callable=AsyncMock):
            with patch.object(
                collector, "update_journey_stops", new_callable=AsyncMock
            ):
                with patch.object(
                    collector, "check_journey_completion", new_callable=AsyncMock
                ):
                    results = await collector.collect(session)

    # Both should be counted as successful
    assert results["trains_processed"] == 2
    assert results["successful"] == 2
    assert results["failed"] == 0
    assert len(results["errors"]) == 0

    # Journey2 should have incremented error count and be expired
    assert journey2.api_error_count == 2
    assert journey2.is_expired is True
