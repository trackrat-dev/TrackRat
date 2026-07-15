"""Test expired train functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitNullDataError, TrainNotFoundError
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et


@pytest.mark.asyncio
async def test_train_expiry_after_three_failures():
    """Test that trains are marked as expired after 3 TrainNotFoundError failures."""
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

    # Mock session.execute for _attempt_completion_on_expiry queries
    mock_result = AsyncMock()
    scalars_mock = Mock()
    scalars_mock.all = Mock(return_value=[])  # No stops found — skip completion
    mock_result.scalars = Mock(return_value=scalars_mock)
    session.execute = AsyncMock(return_value=mock_result)

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

    # Second failure - should increment but still not expire
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 2
    assert journey.is_expired is False

    # Third failure - should expire the train
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 3
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
    session.delete = AsyncMock()  # session.delete is async in newer SQLAlchemy

    # Mock dialect detection for INSERT ON CONFLICT DO NOTHING
    mock_dialect = Mock()
    mock_dialect.name = "postgresql"
    mock_bind = Mock()
    mock_bind.dialect = mock_dialect
    session.bind = mock_bind

    # Mock for multiple session.execute calls - need to handle many calls for stops, deletes, etc.
    mock_result_generic = AsyncMock()
    mock_result_generic.scalar = AsyncMock(return_value=None)
    mock_result_generic.scalar_one_or_none = Mock(return_value=None)
    mock_result_generic.fetchall = Mock(
        return_value=[]
    )  # fetchall should return empty list

    # For scalars(), return a mock that directly returns an empty list (not awaitable)
    scalars_mock = Mock()
    scalars_mock.all.return_value = []
    mock_result_generic.scalars = Mock(return_value=scalars_mock)

    # Mock both execute and scalar methods
    session.execute = AsyncMock(return_value=mock_result_generic)

    # scalar must return JourneyStop-like mocks for update_journey_stops lookups
    # (the new ON CONFLICT path re-fetches after INSERT, so None would break)
    def _make_mock_stop():
        s = Mock()
        s.scheduled_arrival = None
        s.scheduled_departure = None
        s.actual_departure = None
        s.actual_arrival = None
        s.has_departed_station = False
        s.departure_source = None
        s.updated_arrival = None
        s.updated_departure = None
        s.stop_sequence = 0
        s.station_code = ""
        s.pickup_only = False
        s.dropoff_only = False
        s.track = None
        s.track_assigned_at = None
        s.raw_njt_departed_flag = None
        return s

    session.scalar = AsyncMock(side_effect=lambda stmt: _make_mock_stop())

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
async def test_null_data_response_does_not_increment_error_count():
    """Test that NJTransitNullDataError does NOT increment api_error_count.

    When the NJT API returns a response with all key fields null, it's a
    transient API issue — the train likely still appears on departure boards.
    This must NOT count toward the 3-strike expiry threshold.
    """
    journey = TrainJourney(
        id=1,
        train_id="744",
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

    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()

    # Mock NJT client that raises NJTransitNullDataError (transient null data)
    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=NJTransitNullDataError(
            "Train 744 - API returned null data (transient)"
        )
    )

    collector = JourneyCollector(njt_client)

    # Call collect_journey_details multiple times
    for _ in range(5):
        await collector.collect_journey_details(session, journey)

    # api_error_count must remain 0 — null data responses are NOT errors
    assert journey.api_error_count == 0, (
        f"api_error_count should be 0 but was {journey.api_error_count}. "
        "NJTransitNullDataError must not increment the error counter."
    )
    assert journey.is_expired is False, (
        "Train should NOT be expired after null data responses. "
        "The train still appears on NJT departure boards."
    )
    # session.flush should NOT have been called (no state changes)
    assert not session.flush.called, (
        "session.flush should not be called for null data responses "
        "since no database fields are modified."
    )


@pytest.mark.asyncio
async def test_null_data_does_not_reset_existing_error_count():
    """Test that NJTransitNullDataError preserves the existing api_error_count.

    If a train already has 2 genuine TrainNotFoundError strikes, a subsequent
    null data response should NOT reset the counter — it should leave it as-is.
    """
    journey = TrainJourney(
        id=1,
        train_id="738",
        journey_date=now_et().date(),
        line_code="NE",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        scheduled_departure=now_et() - timedelta(hours=1),
        data_source="NJT",
        has_complete_journey=True,
        api_error_count=2,  # Already has 2 genuine errors
        is_expired=False,
    )

    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()

    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=NJTransitNullDataError(
            "Train 738 - API returned null data (transient)"
        )
    )

    collector = JourneyCollector(njt_client)
    await collector.collect_journey_details(session, journey)

    # Error count should remain at 2 — null data doesn't change it
    assert journey.api_error_count == 2, (
        f"api_error_count should remain at 2 but was {journey.api_error_count}. "
        "Null data responses must not modify the error counter."
    )
    assert journey.is_expired is False


@pytest.mark.asyncio
async def test_genuine_not_found_still_expires_after_null_data():
    """Test that genuine TrainNotFoundError still works after null data responses.

    Scenario: train gets null data responses (ignored), then genuine not-found
    responses. Only the genuine ones should count toward expiry.
    """
    journey = TrainJourney(
        id=1,
        train_id="736",
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

    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()

    # Mock session.execute for _attempt_completion_on_expiry queries
    mock_result = AsyncMock()
    scalars_mock = Mock()
    scalars_mock.all = Mock(return_value=[])  # No stops found — skip completion
    mock_result.scalars = Mock(return_value=scalars_mock)
    session.execute = AsyncMock(return_value=mock_result)

    njt_client = AsyncMock()
    collector = JourneyCollector(njt_client)

    # 3 null data responses — should NOT count
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=NJTransitNullDataError("null data")
    )
    for _ in range(3):
        await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 0
    assert journey.is_expired is False

    # Now 2 genuine not-found responses — should count but not yet expire
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=TrainNotFoundError("Train not found")
    )
    await collector.collect_journey_details(session, journey)
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 2
    assert journey.is_expired is False

    # 1 more null data response — should NOT push to expiry
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=NJTransitNullDataError("null data")
    )
    await collector.collect_journey_details(session, journey)

    assert (
        journey.api_error_count == 2
    ), "Null data response must not increment error count past 2"
    assert journey.is_expired is False

    # 1 more genuine not-found — THIS should expire
    njt_client.get_train_stop_list = AsyncMock(
        side_effect=TrainNotFoundError("Train not found")
    )
    await collector.collect_journey_details(session, journey)

    assert journey.api_error_count == 3
    assert journey.is_expired is True
