"""
Tests for Amtrak track cross-referencing from NJT station data.

NJT's getTrainSchedule API returns track assignments for all trains at shared
stations (e.g., NY Penn), including Amtrak trains. The cross-reference function
captures this data and applies it to Amtrak journey stops.

This is important because Amtrak's own API rarely provides platform data,
while NJT's departure board data reliably includes track assignments.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, Mock, patch

from trackrat.collectors.njt.discovery import (
    TrainDiscoveryCollector,
    apply_amtrak_track_from_njt,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET


class TestApplyAmtrakTrackFromNjt:
    """Tests for the apply_amtrak_track_from_njt cross-reference function."""

    @pytest.mark.asyncio
    async def test_sets_track_on_existing_stop(self):
        """When an Amtrak journey and stop exist with no track,
        the NJT-sourced track should be applied."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        stop = JourneyStop(
            journey_id=42,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            track=None,
            track_assigned_at=None,
        )

        session = AsyncMock()
        # First scalar: journey lookup. Second scalar: stop lookup.
        session.scalar = AsyncMock(side_effect=[journey, stop])

        with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2026, 3, 29, 17, 0))

            result = await apply_amtrak_track_from_njt(
                session, "A2150", "NY", "8", source="njt_discovery"
            )

        assert result is True
        assert stop.track == "8"
        assert stop.track_assigned_at is not None

    @pytest.mark.asyncio
    async def test_updates_track_on_reassignment(self):
        """When a stop already has track '5' and NJT returns '8',
        the track should be updated (legitimate reassignment)."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        stop = JourneyStop(
            journey_id=42,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            track="5",
            track_assigned_at=ET.localize(datetime(2026, 3, 29, 16, 0)),
        )

        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[journey, stop])

        with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2026, 3, 29, 17, 0))

            result = await apply_amtrak_track_from_njt(
                session, "A2150", "NY", "8", source="njt_discovery"
            )

        assert result is True
        assert stop.track == "8"

    @pytest.mark.asyncio
    async def test_no_op_when_track_already_matches(self):
        """When stop already has the same track, no update needed."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        stop = JourneyStop(
            journey_id=42,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            track="8",
            track_assigned_at=ET.localize(datetime(2026, 3, 29, 16, 0)),
        )

        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[journey, stop])

        result = await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "8", source="njt_discovery"
        )

        assert result is False
        assert stop.track == "8"  # unchanged

    @pytest.mark.asyncio
    async def test_skips_when_no_amtrak_journey(self):
        """When no Amtrak journey exists for the train, return False."""
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)  # No journey found

        result = await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "8", source="njt_discovery"
        )

        assert result is False
        # Only one scalar call (journey lookup), no stop lookup
        assert session.scalar.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_no_matching_stop(self):
        """When journey exists but no stop for this station, return False."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        session = AsyncMock()
        # Journey found, but no stop
        session.scalar = AsyncMock(side_effect=[journey, None])

        result = await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "8", source="njt_discovery"
        )

        assert result is False
        assert session.scalar.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_track_empty(self):
        """When NJT returns empty or whitespace track, return False."""
        session = AsyncMock()

        result = await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "", source="njt_discovery"
        )

        assert result is False
        # No DB calls should be made
        assert session.scalar.call_count == 0

    @pytest.mark.asyncio
    async def test_skips_when_track_none_like(self):
        """When NJT returns whitespace-only track, return False."""
        session = AsyncMock()

        result = await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "   ", source="njt_discovery"
        )

        assert result is False
        assert session.scalar.call_count == 0

    @pytest.mark.asyncio
    async def test_sanitizes_track_value(self):
        """Track values should be sanitized before storing."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        stop = JourneyStop(
            journey_id=42,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            track=None,
            track_assigned_at=None,
        )

        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[journey, stop])

        with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2026, 3, 29, 17, 0))

            result = await apply_amtrak_track_from_njt(
                session, "A2150", "NY", " 8 ", source="njt_discovery"
            )

        assert result is True
        assert stop.track == "8"  # whitespace stripped by sanitize_track

    @pytest.mark.asyncio
    async def test_preserves_existing_track_assigned_at(self):
        """When track is reassigned, track_assigned_at should be preserved
        if it was already set (it records the first assignment)."""
        journey = Mock(spec=TrainJourney)
        journey.id = 42

        original_time = ET.localize(datetime(2026, 3, 29, 16, 0))
        stop = JourneyStop(
            journey_id=42,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            track="5",
            track_assigned_at=original_time,
        )

        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[journey, stop])

        with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2026, 3, 29, 17, 0))

            await apply_amtrak_track_from_njt(
                session, "A2150", "NY", "8", source="njt_discovery"
            )

        assert stop.track == "8"
        # track_assigned_at preserved from first assignment
        assert stop.track_assigned_at == original_time

    @pytest.mark.asyncio
    async def test_source_parameter_passed_through(self):
        """The source parameter should appear in log messages for diagnostics."""
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)

        # Test both source values work without error
        await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "8", source="njt_discovery"
        )
        await apply_amtrak_track_from_njt(
            session, "A2150", "NY", "8", source="njt_jit"
        )


class TestDiscoveryAmtrakCrossReference:
    """Tests for cross-reference integration in the discovery collector."""

    @pytest.mark.asyncio
    async def test_discovery_cross_references_amtrak_track(self):
        """When NJT discovery encounters an Amtrak train with TRACK data,
        it should call the cross-reference function before skipping."""
        mock_njt_client = AsyncMock()
        collector = TrainDiscoveryCollector(mock_njt_client)

        session = AsyncMock()
        session.add = Mock()
        session.scalar = AsyncMock(return_value=None)

        trains_data = [
            {
                "TRAIN_ID": "A2150",
                "SCHED_DEP_DATE": "29-Mar-2026 05:00:00 PM",
                "DESTINATION": "Washington",
                "TRACK": "7",  # Track data available
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.apply_amtrak_track_from_njt"
        ) as mock_cross_ref:
            mock_cross_ref.return_value = True

            result = await collector.process_discovered_trains(
                session, "NY", trains_data
            )

        # No NJT journeys created for Amtrak trains
        assert result == set()
        assert session.add.call_count == 0

        # Cross-reference was called
        mock_cross_ref.assert_called_once_with(
            session, "A2150", "NY", "7", source="njt_discovery"
        )

    @pytest.mark.asyncio
    async def test_discovery_skips_cross_ref_when_no_track(self):
        """Amtrak trains without TRACK data should be skipped without
        calling the cross-reference function."""
        mock_njt_client = AsyncMock()
        collector = TrainDiscoveryCollector(mock_njt_client)

        session = AsyncMock()
        session.add = Mock()

        trains_data = [
            {
                "TRAIN_ID": "A2150",
                "SCHED_DEP_DATE": "29-Mar-2026 05:00:00 PM",
                "DESTINATION": "Washington",
                # No TRACK field
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.apply_amtrak_track_from_njt"
        ) as mock_cross_ref:
            result = await collector.process_discovered_trains(
                session, "NY", trains_data
            )

        assert result == set()
        mock_cross_ref.assert_not_called()

    @pytest.mark.asyncio
    async def test_discovery_still_processes_njt_trains(self):
        """NJT trains should still be processed normally alongside
        Amtrak cross-referencing."""
        mock_njt_client = AsyncMock()
        collector = TrainDiscoveryCollector(mock_njt_client)

        session = AsyncMock()
        session.add = Mock()
        # Return None for all scalar calls (no existing journeys)
        session.scalar = AsyncMock(return_value=None)
        session.flush = AsyncMock()
        session.begin_nested = lambda: _mock_savepoint()

        trains_data = [
            {
                "TRAIN_ID": "A2150",
                "SCHED_DEP_DATE": "29-Mar-2026 05:00:00 PM",
                "DESTINATION": "Washington",
                "TRACK": "7",
            },
            {
                "TRAIN_ID": "3840",
                "SCHED_DEP_DATE": "29-Mar-2026 05:30:00 PM",
                "DESTINATION": "Trenton",
                "LINE": "Northeast Corridor",
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.apply_amtrak_track_from_njt"
        ) as mock_cross_ref:
            mock_cross_ref.return_value = True

            with patch(
                "trackrat.collectors.njt.discovery.parse_njt_time"
            ) as mock_parse_time:
                mock_parse_time.return_value = datetime(2026, 3, 29, 17, 30)

                with patch(
                    "trackrat.collectors.njt.discovery.now_et"
                ) as mock_now:
                    mock_now.return_value = datetime(2026, 3, 29, 16, 0)

                    result = await collector.process_discovered_trains(
                        session, "NY", trains_data
                    )

        # Only NJT train processed
        assert "3840" in result
        assert "A2150" not in result

        # Amtrak cross-reference called
        mock_cross_ref.assert_called_once()

        # NJT train got normal processing (parse_njt_time called once for NJT train)
        assert mock_parse_time.call_count == 1

    @pytest.mark.asyncio
    async def test_cross_ref_failure_does_not_break_discovery(self):
        """If cross-reference raises an exception, discovery should
        continue processing other trains."""
        mock_njt_client = AsyncMock()
        collector = TrainDiscoveryCollector(mock_njt_client)

        session = AsyncMock()
        session.add = Mock()
        session.scalar = AsyncMock(return_value=None)
        session.flush = AsyncMock()
        session.begin_nested = lambda: _mock_savepoint()

        trains_data = [
            {
                "TRAIN_ID": "A2150",
                "SCHED_DEP_DATE": "29-Mar-2026 05:00:00 PM",
                "DESTINATION": "Washington",
                "TRACK": "7",
            },
            {
                "TRAIN_ID": "3840",
                "SCHED_DEP_DATE": "29-Mar-2026 05:30:00 PM",
                "DESTINATION": "Trenton",
                "LINE": "Northeast Corridor",
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.apply_amtrak_track_from_njt"
        ) as mock_cross_ref:
            # Cross-reference raises an error
            mock_cross_ref.side_effect = Exception("DB error")

            with patch(
                "trackrat.collectors.njt.discovery.parse_njt_time"
            ) as mock_parse_time:
                mock_parse_time.return_value = datetime(2026, 3, 29, 17, 30)

                with patch(
                    "trackrat.collectors.njt.discovery.now_et"
                ) as mock_now:
                    mock_now.return_value = datetime(2026, 3, 29, 16, 0)

                    result = await collector.process_discovered_trains(
                        session, "NY", trains_data
                    )

        # NJT train should still be processed despite cross-ref failure
        assert "3840" in result


# Helper for savepoint mocking
from contextlib import asynccontextmanager


@asynccontextmanager
async def _mock_savepoint():
    yield
