"""
Tests for the prefetched_train_data parameter on collect_journey_details.

The batch collector pre-fetches NJT API data in Phase 2, then passes it
to collect_journey_details in Phase 3 to avoid a redundant API call.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.api import NJTransitTrainData
from trackrat.models.database import TrainJourney


def _make_minimal_train_data() -> NJTransitTrainData:
    """Create minimal valid train data with empty stops."""
    return NJTransitTrainData(
        TRAIN_ID="1234",
        LINECODE="NE",
        BACKCOLOR="#000000",
        FORECOLOR="#FFFFFF",
        SHADOWCOLOR="#CCCCCC",
        DESTINATION="Trenton",
        TRANSFERAT="",
        STOPS=[],
    )


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
    journey.has_complete_journey = False
    journey.origin_station_code = None
    journey.api_error_count = 0

    prefetched = _make_minimal_train_data()

    # Mock internal methods to prevent them from running.
    # We only care about whether the API call is made or skipped.
    with (
        patch.object(collector, "_is_same_journey", new_callable=AsyncMock, return_value=True),
        patch.object(collector, "enhance_with_departure_board_data", new_callable=AsyncMock),
        patch.object(collector, "create_journey_snapshot", new_callable=AsyncMock),
        patch.object(collector, "update_journey_metadata", new_callable=AsyncMock),
        patch.object(collector, "update_journey_stops", new_callable=AsyncMock),
        patch.object(collector, "check_journey_completion", new_callable=AsyncMock),
    ):
        session = AsyncMock()
        session.flush = AsyncMock()

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await collector.collect_journey_details(
            session, journey, prefetched_train_data=prefetched
        )

    # The NJT API should NOT have been called
    njt_client.get_train_stop_list.assert_not_called()


@pytest.mark.asyncio
async def test_without_prefetched_data_calls_api():
    """When prefetched_train_data is None (default), the NJT API IS called."""
    njt_client = AsyncMock()
    njt_client.get_train_stop_list = AsyncMock(return_value=_make_minimal_train_data())

    collector = JourneyCollector(njt_client)

    journey = Mock(spec=TrainJourney)
    journey.id = 1
    journey.train_id = "1234"
    journey.destination = "Trenton"
    journey.line_code = "NE"
    journey.has_complete_journey = False
    journey.origin_station_code = None
    journey.api_error_count = 0

    with (
        patch.object(collector, "_is_same_journey", new_callable=AsyncMock, return_value=True),
        patch.object(collector, "enhance_with_departure_board_data", new_callable=AsyncMock),
        patch.object(collector, "create_journey_snapshot", new_callable=AsyncMock),
        patch.object(collector, "update_journey_metadata", new_callable=AsyncMock),
        patch.object(collector, "update_journey_stops", new_callable=AsyncMock),
        patch.object(collector, "check_journey_completion", new_callable=AsyncMock),
    ):
        session = AsyncMock()
        session.flush = AsyncMock()

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await collector.collect_journey_details(session, journey)

    # The NJT API SHOULD have been called
    njt_client.get_train_stop_list.assert_called_once_with("1234")
