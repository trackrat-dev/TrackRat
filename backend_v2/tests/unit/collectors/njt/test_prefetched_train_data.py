"""
Tests for the prefetched_train_data parameter on collect_journey_details.

The batch collector pre-fetches NJT API data in Phase 2, then passes it
to collect_journey_details in Phase 3 to avoid a redundant API call.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney


@pytest.mark.asyncio
async def test_prefetched_data_skips_api_call():
    """When prefetched_train_data is provided, the NJT API should NOT be called."""
    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock()

    collector = JourneyCollector(njt_client)

    journey = Mock(spec=TrainJourney)
    journey.id = 1
    journey.train_id = "1234"
    journey.destination = "Trenton"
    journey.line_code = "NE"
    journey.line_color = "#000"
    journey.has_complete_journey = False
    journey.stops_count = 0
    journey.update_count = 0
    journey.api_error_count = 0
    journey.is_completed = False
    journey.is_cancelled = False
    journey.scheduled_departure = None
    journey.scheduled_arrival = None
    journey.origin_station_code = None
    journey.terminal_station_code = None
    journey.last_updated_at = None
    journey.journey_date = None
    journey.observation_type = "OBSERVED"

    # Create minimal prefetched train data
    from trackrat.models.api import NJTransitTrainData

    prefetched = NJTransitTrainData(
        TRAIN_ID="1234",
        LINECODE="NE",
        BACKCOLOR="#000000",
        FORECOLOR="#FFFFFF",
        SHADOWCOLOR="#CCCCCC",
        DESTINATION="Trenton",
        TRANSFERAT="",
        STOPS=[],
    )

    # Mock session — collect_journey_details with empty STOPS will
    # skip most processing but still call _is_same_journey etc.
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = Mock()

    mock_result = Mock()
    mock_scalars = Mock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    session.execute = AsyncMock(return_value=mock_result)
    session.scalar = AsyncMock(return_value=None)

    # Mock dialect for the upsert
    mock_bind = Mock()
    mock_bind.dialect.name = "postgresql"
    session.bind = mock_bind

    await collector.collect_journey_details(
        session, journey, prefetched_train_data=prefetched
    )

    # The NJT API should NOT have been called
    njt_client.get_train_stop_list.assert_not_called()


@pytest.mark.asyncio
async def test_without_prefetched_data_calls_api():
    """When prefetched_train_data is None (default), the NJT API IS called."""
    from trackrat.collectors.njt.client import TrainNotFoundError
    from trackrat.models.api import NJTransitTrainData

    njt_client = AsyncMock()
    train_data = NJTransitTrainData(
        TRAIN_ID="1234",
        LINECODE="NE",
        BACKCOLOR="#000000",
        FORECOLOR="#FFFFFF",
        SHADOWCOLOR="#CCCCCC",
        DESTINATION="Trenton",
        TRANSFERAT="",
        STOPS=[],
    )
    njt_client.get_train_stop_list = AsyncMock(return_value=train_data)

    collector = JourneyCollector(njt_client)

    journey = Mock(spec=TrainJourney)
    journey.id = 1
    journey.train_id = "1234"
    journey.destination = "Trenton"
    journey.line_code = "NE"
    journey.line_color = "#000"
    journey.has_complete_journey = False
    journey.stops_count = 0
    journey.update_count = 0
    journey.api_error_count = 0
    journey.is_completed = False
    journey.is_cancelled = False
    journey.scheduled_departure = None
    journey.scheduled_arrival = None
    journey.origin_station_code = None
    journey.terminal_station_code = None
    journey.last_updated_at = None
    journey.journey_date = None
    journey.observation_type = "OBSERVED"

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = Mock()

    mock_result = Mock()
    mock_scalars = Mock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    session.execute = AsyncMock(return_value=mock_result)
    session.scalar = AsyncMock(return_value=None)

    mock_bind = Mock()
    mock_bind.dialect.name = "postgresql"
    session.bind = mock_bind

    await collector.collect_journey_details(session, journey)

    # The NJT API SHOULD have been called
    njt_client.get_train_stop_list.assert_called_once_with("1234")
