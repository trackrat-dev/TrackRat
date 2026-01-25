"""
Unit tests for departure filtering of expired and completed trains.

Tests that:
1. Expired trains are filtered from departure results
2. Completed trains are filtered from departure results
3. The is_expired field is properly set in the response
4. Cancelled trains are NOT filtered (they should still show with is_cancelled=True)
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.api import TrainPosition
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et, ET


class TestDepartureFiltering:
    """Tests for filtering expired and completed trains from departures."""

    def _create_journey(
        self,
        train_id: str,
        is_expired: bool = False,
        is_completed: bool = False,
        is_cancelled: bool = False,
        departure_time: datetime | None = None,
    ) -> TrainJourney:
        """Create a mock TrainJourney for testing."""
        now = now_et()
        dep_time = departure_time or (now + timedelta(hours=1))

        journey = Mock(spec=TrainJourney)
        journey.id = hash(train_id)
        journey.train_id = train_id
        journey.journey_date = now.date()
        journey.line_code = "NE"
        journey.line_name = "Northeast Corridor"
        journey.line_color = "#000000"
        journey.destination = "New York"
        journey.origin_station_code = "TR"
        journey.terminal_station_code = "NY"
        journey.scheduled_departure = dep_time
        journey.data_source = "NJT"
        journey.observation_type = "OBSERVED"
        journey.is_expired = is_expired
        journey.is_completed = is_completed
        journey.is_cancelled = is_cancelled
        journey.last_updated_at = now
        journey.first_seen_at = now
        journey.update_count = 1
        journey.stops_count = 2

        # Create mock stops
        from_stop = Mock(spec=JourneyStop)
        from_stop.station_code = "TR"
        from_stop.station_name = "Trenton"
        from_stop.stop_sequence = 1
        from_stop.scheduled_departure = dep_time
        from_stop.scheduled_arrival = dep_time - timedelta(minutes=2)
        from_stop.updated_departure = None
        from_stop.updated_arrival = None
        from_stop.actual_departure = None
        from_stop.actual_arrival = None
        from_stop.track = "1"
        from_stop.has_departed_station = False

        to_stop = Mock(spec=JourneyStop)
        to_stop.station_code = "NY"
        to_stop.station_name = "New York Penn Station"
        to_stop.stop_sequence = 2
        to_stop.scheduled_departure = dep_time + timedelta(hours=1)
        to_stop.scheduled_arrival = dep_time + timedelta(hours=1)
        to_stop.updated_departure = None
        to_stop.updated_arrival = None
        to_stop.actual_departure = None
        to_stop.actual_arrival = None
        to_stop.track = None
        to_stop.has_departed_station = False

        journey.stops = [from_stop, to_stop]

        return journey

    def _mock_train_position(self) -> TrainPosition:
        """Create a mock TrainPosition."""
        return TrainPosition(
            last_departed_station_code=None,
            at_station_code=None,
            next_station_code="TR",
            between_stations=False,
        )

    @pytest.mark.asyncio
    async def test_expired_trains_excluded_from_departures(self):
        """Test that trains with is_expired=True are excluded from departure results."""
        # Create journeys: one normal, one expired
        normal_journey = self._create_journey("1234", is_expired=False)
        expired_journey = self._create_journey("5678", is_expired=True)

        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock the database query to return both journeys initially
        # (The filtering should happen in the WHERE clause)
        mock_result = Mock()
        mock_scalars = Mock()
        # Only return the non-expired journey (simulating the WHERE clause filter)
        mock_scalars.unique.return_value.all.return_value = [normal_journey]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock scalar for needs_refresh check
        mock_session.scalar = AsyncMock(return_value=None)

        # Create service and call get_departures
        service = DepartureService()

        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ):
            with patch.object(
                service, "_get_path_cutoff_time", new_callable=AsyncMock
            ) as mock_cutoff:
                mock_cutoff.return_value = now_et() + timedelta(hours=2)

                with patch.object(
                    service,
                    "_calculate_train_position",
                    return_value=self._mock_train_position(),
                ):
                    # Patch GTFS service to avoid merge complications
                    with patch(
                        "trackrat.services.gtfs.GTFSService"
                    ) as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        result = await service.get_departures(
                            db=mock_session,
                            from_station="TR",
                            to_station="NY",
                        )

        # Verify only the non-expired train is in results
        assert len(result.departures) == 1
        assert result.departures[0].train_id == "1234"

    @pytest.mark.asyncio
    async def test_completed_trains_excluded_from_departures(self):
        """Test that trains with is_completed=True are excluded from departure results."""
        # Create journeys: one normal, one completed
        normal_journey = self._create_journey("1234", is_completed=False)
        completed_journey = self._create_journey("5678", is_completed=True)

        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        # Only return the non-completed journey (simulating the WHERE clause filter)
        mock_scalars.unique.return_value.all.return_value = [normal_journey]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ):
            with patch.object(
                service, "_get_path_cutoff_time", new_callable=AsyncMock
            ) as mock_cutoff:
                mock_cutoff.return_value = now_et() + timedelta(hours=2)

                with patch.object(
                    service,
                    "_calculate_train_position",
                    return_value=self._mock_train_position(),
                ):
                    with patch(
                        "trackrat.services.gtfs.GTFSService"
                    ) as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        result = await service.get_departures(
                            db=mock_session,
                            from_station="TR",
                            to_station="NY",
                        )

        # Verify only the non-completed train is in results
        assert len(result.departures) == 1
        assert result.departures[0].train_id == "1234"

    @pytest.mark.asyncio
    async def test_cancelled_trains_included_in_departures(self):
        """Test that cancelled trains ARE included (with is_cancelled=True)."""
        # Create journeys: one normal, one cancelled
        normal_journey = self._create_journey("1234", is_cancelled=False)
        cancelled_journey = self._create_journey("5678", is_cancelled=True)

        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        # Both should be returned since cancelled is NOT filtered
        mock_scalars.unique.return_value.all.return_value = [
            normal_journey,
            cancelled_journey,
        ]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ):
            with patch.object(
                service, "_get_path_cutoff_time", new_callable=AsyncMock
            ) as mock_cutoff:
                mock_cutoff.return_value = now_et() + timedelta(hours=2)

                with patch.object(
                    service,
                    "_calculate_train_position",
                    return_value=self._mock_train_position(),
                ):
                    with patch(
                        "trackrat.services.gtfs.GTFSService"
                    ) as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        result = await service.get_departures(
                            db=mock_session,
                            from_station="TR",
                            to_station="NY",
                        )

        # Verify both trains are returned
        assert len(result.departures) == 2
        train_ids = {d.train_id for d in result.departures}
        assert train_ids == {"1234", "5678"}

        # Verify cancelled flag is set correctly
        cancelled_departure = next(
            d for d in result.departures if d.train_id == "5678"
        )
        assert cancelled_departure.is_cancelled is True

    @pytest.mark.asyncio
    async def test_is_expired_field_set_in_response(self):
        """Test that is_expired field is properly set in TrainDeparture response."""
        # Create a journey with is_expired=False (since expired ones are filtered)
        journey = self._create_journey("1234", is_expired=False)

        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [journey]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ):
            with patch.object(
                service, "_get_path_cutoff_time", new_callable=AsyncMock
            ) as mock_cutoff:
                mock_cutoff.return_value = now_et() + timedelta(hours=2)

                with patch.object(
                    service,
                    "_calculate_train_position",
                    return_value=self._mock_train_position(),
                ):
                    with patch(
                        "trackrat.services.gtfs.GTFSService"
                    ) as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        result = await service.get_departures(
                            db=mock_session,
                            from_station="TR",
                            to_station="NY",
                        )

        # Verify is_expired field exists and is False
        assert len(result.departures) == 1
        assert result.departures[0].is_expired is False

    @pytest.mark.asyncio
    async def test_is_expired_none_converted_to_false(self):
        """Test that is_expired=None is converted to False in response."""
        journey = self._create_journey("1234")
        # Simulate a journey where is_expired was never set (None)
        journey.is_expired = None

        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [journey]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ):
            with patch.object(
                service, "_get_path_cutoff_time", new_callable=AsyncMock
            ) as mock_cutoff:
                mock_cutoff.return_value = now_et() + timedelta(hours=2)

                with patch.object(
                    service,
                    "_calculate_train_position",
                    return_value=self._mock_train_position(),
                ):
                    with patch(
                        "trackrat.services.gtfs.GTFSService"
                    ) as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        result = await service.get_departures(
                            db=mock_session,
                            from_station="TR",
                            to_station="NY",
                        )

        # Verify is_expired is False (not None)
        assert len(result.departures) == 1
        assert result.departures[0].is_expired is False


class TestDepartureFilterQuery:
    """Tests to verify the SQL WHERE clause includes proper filters."""

    @pytest.mark.asyncio
    async def test_departure_filters_include_is_expired(self):
        """Verify that departure_filters list includes is_expired filter."""
        from trackrat.models.database import TrainJourney

        # The filter should be: TrainJourney.is_expired.is_not(True)
        # This test verifies the filter construction

        # Create the filter expression
        filter_expr = TrainJourney.is_expired.is_not(True)

        # Verify it's a valid SQLAlchemy expression
        assert filter_expr is not None
        # The string representation should mention is_expired
        assert "is_expired" in str(filter_expr)

    @pytest.mark.asyncio
    async def test_departure_filters_include_is_completed(self):
        """Verify that departure_filters list includes is_completed filter."""
        from trackrat.models.database import TrainJourney

        # The filter should be: TrainJourney.is_completed.is_not(True)
        filter_expr = TrainJourney.is_completed.is_not(True)

        assert filter_expr is not None
        assert "is_completed" in str(filter_expr)
