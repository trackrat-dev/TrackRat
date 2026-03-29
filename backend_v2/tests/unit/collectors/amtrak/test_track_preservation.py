"""
Tests for Amtrak track preservation during journey collection.

Verifies that existing track assignments are NOT overwritten with None when
the Amtrak API returns an empty platform field on subsequent collection cycles.

This was a production bug where tracks were briefly visible then wiped out
because _upsert_journey_stop blindly overwrote all fields including track=None.

See: https://github.com/bokonon1/trackrat/issues/XXX
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.api import AmtrakStationData, AmtrakTrainData
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et
from tests.factories.amtrak import (
    create_amtrak_station_data,
    create_amtrak_train_data,
    create_amtrak_journey,
    create_amtrak_journey_stop,
)


@pytest.fixture
def collector():
    """Create an AmtrakJourneyCollector instance."""
    return AmtrakJourneyCollector()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


def _make_existing_stop(
    station_code: str = "NY",
    track: str | None = None,
    track_assigned_at: datetime | None = None,
    journey_id: int = 1,
) -> JourneyStop:
    """Create a JourneyStop with specific track state for testing."""
    stop = JourneyStop(
        journey_id=journey_id,
        station_code=station_code,
        station_name="Test Station",
        stop_sequence=0,
        track=track,
        track_assigned_at=track_assigned_at,
    )
    return stop


class TestUpsertJourneyStopTrackPreservation:
    """Tests for _upsert_journey_stop track preservation logic."""

    @pytest.mark.asyncio
    async def test_preserves_existing_track_when_api_returns_none(
        self, collector, mock_session
    ):
        """When a stop already has track='8' and new data has track=None,
        the existing track MUST be preserved. This is the core bug fix."""
        existing_stop = _make_existing_stop(
            station_code="NY",
            track="8",
            track_assigned_at=ET.localize(datetime(2026, 3, 28, 18, 0)),
        )
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        stop_data = {
            "station_name": "New York Penn Station",
            "stop_sequence": 5,
            "scheduled_arrival": ET.localize(datetime(2026, 3, 28, 18, 25)),
            "has_departed_station": True,
            "raw_amtrak_status": "Departed",
            "track": None,  # Amtrak API returned empty platform
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NY", stop_data=stop_data
        )

        assert result.track == "8", (
            "Existing track '8' was overwritten with None! "
            "The Amtrak collector must preserve tracks when the API returns empty platform."
        )
        assert result.track_assigned_at is not None

    @pytest.mark.asyncio
    async def test_sets_track_when_no_existing_track(self, collector, mock_session):
        """When a stop has no track and new data provides one, it should be set."""
        existing_stop = _make_existing_stop(station_code="NY", track=None)
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        stop_data = {
            "station_name": "New York Penn Station",
            "stop_sequence": 5,
            "has_departed_station": False,
            "raw_amtrak_status": "Station",
            "track": "13",
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NY", stop_data=stop_data
        )

        assert result.track == "13"
        assert result.track_assigned_at is not None

    @pytest.mark.asyncio
    async def test_updates_track_when_reassigned(self, collector, mock_session):
        """When a stop has track='5' and API provides track='8' (reassignment),
        the new track should be used."""
        existing_stop = _make_existing_stop(
            station_code="NY",
            track="5",
            track_assigned_at=ET.localize(datetime(2026, 3, 28, 17, 0)),
        )
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        stop_data = {
            "station_name": "New York Penn Station",
            "stop_sequence": 5,
            "has_departed_station": False,
            "raw_amtrak_status": "Station",
            "track": "8",  # Platform reassignment
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NY", stop_data=stop_data
        )

        assert result.track == "8", "Track should update when API provides a new value"

    @pytest.mark.asyncio
    async def test_creates_new_stop_with_track(self, collector, mock_session):
        """When no existing stop exists and data has a track, create with track."""
        mock_session.scalar = AsyncMock(return_value=None)

        stop_data = {
            "station_name": "New Haven",
            "stop_sequence": 3,
            "has_departed_station": True,
            "raw_amtrak_status": "Departed",
            "track": "8",
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NHV", stop_data=stop_data
        )

        assert result.track == "8"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_stop_without_track(self, collector, mock_session):
        """When no existing stop exists and data has no track, create without."""
        mock_session.scalar = AsyncMock(return_value=None)

        stop_data = {
            "station_name": "New Haven",
            "stop_sequence": 3,
            "has_departed_station": False,
            "raw_amtrak_status": "Enroute",
            "track": None,
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NHV", stop_data=stop_data
        )

        assert result.track is None
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_track_across_multiple_updates(
        self, collector, mock_session
    ):
        """Simulate multiple collection cycles: track assigned, then API returns None
        repeatedly. Track must survive all cycles."""
        existing_stop = _make_existing_stop(
            station_code="STM",
            track="3",
            track_assigned_at=ET.localize(datetime(2026, 3, 28, 17, 0)),
        )
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        # Simulate 3 collection cycles where Amtrak returns empty platform
        for cycle in range(3):
            stop_data = {
                "station_name": "Stamford",
                "stop_sequence": 2,
                "has_departed_station": True,
                "raw_amtrak_status": "Departed",
                "track": None,
            }

            result = await collector._upsert_journey_stop(
                mock_session,
                journey_id=1,
                station_code="STM",
                stop_data=stop_data,
            )

            assert result.track == "3", (
                f"Track lost after collection cycle {cycle + 1}! "
                "Track must be preserved across multiple API calls with empty platform."
            )

    @pytest.mark.asyncio
    async def test_no_track_fields_dont_block_other_updates(
        self, collector, mock_session
    ):
        """When track is preserved, other fields should still be updated normally."""
        existing_stop = _make_existing_stop(station_code="NY", track="13")
        existing_stop.has_departed_station = False
        existing_stop.raw_amtrak_status = "Enroute"
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        stop_data = {
            "station_name": "New York Penn Station",
            "stop_sequence": 5,
            "has_departed_station": True,  # Train departed
            "raw_amtrak_status": "Departed",  # Status changed
            "track": None,  # But platform field went empty
        }

        result = await collector._upsert_journey_stop(
            mock_session, journey_id=1, station_code="NY", stop_data=stop_data
        )

        assert result.track == "13", "Track must be preserved"
        assert result.has_departed_station is True, "Departure status must update"
        assert result.raw_amtrak_status == "Departed", "Status must update"


class TestCollectJourneyDetailsTrackPreservation:
    """Tests for track preservation in the collect_journey_details JIT path.

    The collect_journey_details method has its own inline stop update loop
    (separate from _upsert_journey_stop). We test it end-to-end by mocking
    the Amtrak client and database session.
    """

    @pytest.mark.asyncio
    async def test_jit_path_preserves_track_when_platform_empty(self, collector):
        """The collect_journey_details path also must preserve existing tracks
        when Amtrak returns empty platform."""
        # Create an existing stop with a track
        existing_stop = _make_existing_stop(
            station_code="NY",
            track="8",
            track_assigned_at=ET.localize(datetime(2026, 3, 28, 18, 0)),
        )
        existing_stop.journey_id = 1

        # Create existing journey (real object, not MagicMock, so attributes persist)
        journey = TrainJourney(
            id=1,
            train_id="A57",
            journey_date=datetime(2026, 3, 28).date(),
            data_source="AMTRAK",
            line_code="AM",
            line_name="Amtrak",
            observation_type="OBSERVED",
            destination="Washington Union Station",
            origin_station_code="NY",
            terminal_station_code="NY",
            has_complete_journey=True,
            is_cancelled=False,
            is_completed=False,
            is_expired=False,
            api_error_count=0,
            stops_count=1,
        )

        # Create train data where platform is empty (simulating the bug scenario)
        train_data = create_amtrak_train_data(
            train_num="57",
            route="Vermonter",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn Station",
                    sch_arr="2026-03-28T18:25:00-04:00",
                    sch_dep="2026-03-28T19:01:00-04:00",
                    status="Departed",
                    platform="",  # Empty platform - this is the bug trigger
                ),
            ],
        )

        mock_session = AsyncMock()
        # Return the existing stop when queried by station_code
        mock_session.scalar = AsyncMock(return_value=existing_stop)
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.flush = AsyncMock()

        # Mock the client to return the test train data
        mock_client = AsyncMock()
        mock_client.get_all_trains = AsyncMock(
            return_value={"57": [train_data]}
        )
        collector.client = mock_client

        await collector.collect_journey_details(mock_session, journey)

        assert existing_stop.track == "8", (
            "JIT path overwrote existing track with None! "
            "collect_journey_details must preserve tracks when platform is empty."
        )
