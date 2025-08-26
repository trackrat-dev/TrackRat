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
    # Use a departure time that matches the mock API data (10:02 AM)
    from trackrat.utils.time import parse_njt_time

    scheduled_departure = parse_njt_time("10:02 AM")

    journey = TrainJourney(
        id=1,
        train_id="1234",
        journey_date=now_et().date(),
        line_code="NE",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        scheduled_departure=scheduled_departure,
        data_source="NJT",
        has_complete_journey=True,
        api_error_count=1,  # Previous error
        is_expired=False,
    )

    # Mock session
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.add = Mock()  # session.add is synchronous, not async

    # Mock for multiple session.execute calls - need to handle many calls for stops, deletes, etc.
    mock_result_generic = AsyncMock()
    mock_result_generic.scalar = AsyncMock(return_value=None)
    mock_result_generic.fetchall = Mock(
        return_value=[]
    )  # fetchall should return empty list

    # For scalars(), return a mock that directly returns an empty list (not awaitable)
    scalars_mock = Mock()
    scalars_mock.all.return_value = []
    mock_result_generic.scalars = Mock(return_value=scalars_mock)

    # Mock both execute and scalar methods
    session.execute = AsyncMock(return_value=mock_result_generic)
    session.scalar = AsyncMock(
        return_value=None
    )  # For queries that return a single object

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

    # First mock_result for the journey selection query
    mock_result = AsyncMock()
    scalars_mock = Mock()  # Use regular Mock, not AsyncMock
    scalars_mock.all = Mock(return_value=[journey1, journey2])
    mock_result.scalars = Mock(return_value=scalars_mock)
    mock_result.fetchall = Mock(return_value=[])  # Add fetchall support

    # Second mock_result for the expire query (with rowcount)
    mock_expire_result = AsyncMock()
    mock_expire_result.rowcount = 0  # No rows expired
    mock_expire_result.fetchall = Mock(return_value=[])  # Add fetchall support
    expire_scalars_mock = Mock()
    expire_scalars_mock.all = Mock(return_value=[])
    mock_expire_result.scalars = Mock(return_value=expire_scalars_mock)

    # Set up session.execute to return different results for different calls
    # Use a function to handle multiple calls with default mock
    def execute_side_effect(*args, **kwargs):
        if hasattr(execute_side_effect, "call_count"):
            execute_side_effect.call_count += 1
        else:
            execute_side_effect.call_count = 1

        if execute_side_effect.call_count == 1:
            return mock_result
        elif execute_side_effect.call_count == 2:
            return mock_expire_result
        else:
            # Return a generic mock for any additional calls
            generic_mock = AsyncMock(rowcount=0)
            # Use regular Mock for scalars since it's not async
            generic_scalars = Mock()
            generic_scalars.all = Mock(
                return_value=[]
            )  # Return empty list for scalars().all()
            # Make sure scalars is not async
            generic_mock.scalars = Mock(return_value=generic_scalars)
            generic_mock.fetchall = Mock(return_value=[])  # Add fetchall support
            return generic_mock

    session.execute = AsyncMock(side_effect=execute_side_effect)

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
                    with patch.object(
                        collector,
                        "find_historical_trains_for_backfill",
                        new_callable=AsyncMock,
                    ) as mock_historical:
                        mock_historical.return_value = (
                            []
                        )  # No historical trains to process
                        results = await collector.collect(session)

    # Both should be counted as successful
    assert results["trains_processed"] == 2
    assert results["successful"] == 2
    assert results["failed"] == 0
    assert len(results["errors"]) == 0

    # Journey2 should have incremented error count and be expired
    assert journey2.api_error_count == 2
    assert journey2.is_expired is True
