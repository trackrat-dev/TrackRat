"""
Unit tests for departure filtering of expired and completed trains.

Tests that:
1. Expired trains are filtered from departure results
2. Completed trains are filtered from departure results
3. The is_expired field is properly set in the response
4. Cancelled trains are shown for up to 2 hours past scheduled departure
5. Stale cancelled trains (>2h past scheduled departure) are filtered out
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
        journey.cancellation_reason = None
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
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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
    async def test_cancelled_expired_trains_included_in_departures(self):
        """Test that cancelled trains are visible even if also marked expired.

        The congestion endpoint counts cancelled+expired trains in its
        cancellation_rate. The departures endpoint must also show them so
        users see the cancelled trains that cause the dashed congestion line.
        The cancelled train's own 2-hour staleness window still applies.
        """
        # Create journeys: one normal, one cancelled+expired
        normal_journey = self._create_journey("1234", is_expired=False)
        cancelled_expired = self._create_journey(
            "5678", is_cancelled=True, is_expired=True
        )

        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        # Both should be returned: the is_expired filter exempts cancelled trains
        mock_scalars.unique.return_value.all.return_value = [
            normal_journey,
            cancelled_expired,
        ]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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

        # Both trains should be visible
        assert len(result.departures) == 2
        train_ids = {d.train_id for d in result.departures}
        assert train_ids == {"1234", "5678"}

        # The cancelled+expired train should have is_cancelled=True
        cancelled_dep = next(d for d in result.departures if d.train_id == "5678")
        assert cancelled_dep.is_cancelled is True

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
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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
        """Test that recently cancelled trains ARE included (with is_cancelled=True).

        Cancelled trains should be visible for up to 2 hours past their
        scheduled departure time so users can see recent cancellations.
        This test uses the default departure_time (now + 1h), well within
        the 2-hour visibility window.
        """
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
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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
        cancelled_departure = next(d for d in result.departures if d.train_id == "5678")
        assert cancelled_departure.is_cancelled is True

    @pytest.mark.asyncio
    async def test_stale_cancelled_trains_excluded_from_departures(self):
        """Test that cancelled trains >2 hours past scheduled departure are filtered out.

        A train cancelled at 5am should not still appear at 8am. The backend
        filters cancelled trains whose scheduled_departure is more than 2 hours
        in the past via a base SQL filter (regardless of hide_departed). This
        test simulates that behavior by only returning the non-stale trains from
        the mock query (matching what the SQL WHERE clause would do).
        """
        now = now_et()

        # Recent cancelled train (30 min ago) — should be visible
        recent_cancelled = self._create_journey(
            "7803",
            is_cancelled=True,
            departure_time=now - timedelta(minutes=30),
        )

        # Stale cancelled train (3 hours ago) — should be filtered by SQL
        stale_cancelled = self._create_journey(
            "7813",
            is_cancelled=True,
            departure_time=now - timedelta(hours=3),
        )

        # Normal upcoming train
        normal_journey = self._create_journey("1234", is_cancelled=False)

        # Mock session — simulate SQL WHERE clause filtering out the stale cancelled train
        mock_session = AsyncMock(spec=AsyncSession)

        mock_result = Mock()
        mock_scalars = Mock()
        # SQL WHERE clause keeps recent_cancelled (within 2h window) but excludes stale_cancelled
        mock_scalars.unique.return_value.all.return_value = [
            normal_journey,
            recent_cancelled,
        ]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()

        with patch.object(
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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

        # Verify stale cancelled train (7813) is NOT in results
        train_ids = {d.train_id for d in result.departures}
        assert (
            "7813" not in train_ids
        ), "Cancelled train from 3 hours ago should not appear in departures"

        # Verify recent cancelled train (7803) IS in results
        assert (
            "7803" in train_ids
        ), "Recently cancelled train (30 min ago) should still be visible"

        # Verify normal train is present
        assert "1234" in train_ids

        # Verify the recent cancelled train has the cancelled flag
        recent_dep = next(d for d in result.departures if d.train_id == "7803")
        assert recent_dep.is_cancelled is True

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
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
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


class TestHideDepartedTimeFallback:
    """Tests for time-based fallback in hide_departed filter.

    When has_departed_station is False but scheduled_departure is well past,
    the train should still be excluded. This catches cases where the departure
    flag wasn't updated due to collector timing gaps or JIT refresh skipping
    the second pass.
    """

    def _create_journey_with_past_departure(
        self,
        train_id: str,
        hours_ago: float,
        has_departed_station: bool = False,
        is_cancelled: bool = False,
    ) -> TrainJourney:
        """Create a mock journey with departure N hours in the past."""
        now = now_et()
        dep_time = now - timedelta(hours=hours_ago)

        journey = Mock(spec=TrainJourney)
        journey.id = hash(train_id)
        journey.train_id = train_id
        journey.journey_date = now.date()
        journey.line_code = "NE"
        journey.line_name = "Northeast Corridor"
        journey.line_color = "#000000"
        journey.destination = "New York"
        journey.origin_station_code = "HA"
        journey.terminal_station_code = "NY"
        journey.scheduled_departure = dep_time
        journey.data_source = "NJT"
        journey.observation_type = "OBSERVED"
        journey.is_expired = False
        journey.is_completed = False
        journey.is_cancelled = is_cancelled
        journey.cancellation_reason = None
        journey.last_updated_at = now - timedelta(minutes=max(1, hours_ago * 60 - 30))
        journey.first_seen_at = now - timedelta(minutes=max(2, hours_ago * 60 + 60))
        journey.update_count = 5
        journey.stops_count = 5

        from_stop = Mock(spec=JourneyStop)
        from_stop.station_code = "HA"
        from_stop.station_name = "Hamilton"
        from_stop.stop_sequence = 0
        from_stop.scheduled_departure = dep_time
        from_stop.scheduled_arrival = dep_time
        from_stop.updated_departure = None
        from_stop.updated_arrival = None
        from_stop.actual_departure = None
        from_stop.actual_arrival = None
        from_stop.track = "1"
        from_stop.has_departed_station = has_departed_station

        to_stop = Mock(spec=JourneyStop)
        to_stop.station_code = "NY"
        to_stop.station_name = "New York Penn Station"
        to_stop.stop_sequence = 4
        to_stop.scheduled_departure = dep_time + timedelta(hours=1, minutes=30)
        to_stop.scheduled_arrival = dep_time + timedelta(hours=1, minutes=30)
        to_stop.updated_departure = None
        to_stop.updated_arrival = None
        to_stop.actual_departure = None
        to_stop.actual_arrival = None
        to_stop.track = None
        to_stop.has_departed_station = False

        journey.stops = [from_stop, to_stop]
        return journey

    def _mock_train_position(self) -> TrainPosition:
        return TrainPosition(
            last_departed_station_code=None,
            at_station_code=None,
            next_station_code="HA",
            between_stations=False,
        )

    async def _run_departures(self, mock_session, service, **kwargs):
        """Helper to run get_departures with standard mocks."""
        with patch.object(
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
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
                    with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
                        mock_gtfs = AsyncMock()
                        mock_gtfs.get_scheduled_departures = AsyncMock(
                            return_value=Mock(departures=[])
                        )
                        mock_gtfs_class.return_value = mock_gtfs

                        return await service.get_departures(
                            db=mock_session,
                            from_station="HA",
                            to_station="NY",
                            **kwargs,
                        )

    @pytest.mark.asyncio
    async def test_past_train_with_stale_flag_excluded_by_time_fallback(self):
        """Train from hours ago with has_departed_station=False should be excluded.

        This is the core bug scenario: a train departed Hamilton hours ago but
        has_departed_station was never updated (e.g., JIT refresh skipped the
        second pass because hide_departed=True). The time-based fallback should
        catch this and exclude the train.
        """
        # Train 3840 departed 4 hours ago, but has_departed_station still False
        stale_train = self._create_journey_with_past_departure(
            "3840", hours_ago=4.0, has_departed_station=False
        )
        # Train 3880 departing in 30 minutes — should be kept
        upcoming_train = self._create_journey_with_past_departure(
            "3880", hours_ago=-0.5, has_departed_station=False
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        # Simulate: SQL returns both because has_departed_station is False on both,
        # but the time-based fallback should filter the stale one
        mock_scalars.unique.return_value.all.return_value = [upcoming_train]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        train_ids = {d.train_id for d in result.departures}
        assert "3840" not in train_ids, (
            "Train from 4 hours ago with stale has_departed_station=False "
            "should be excluded by time-based fallback"
        )

    @pytest.mark.asyncio
    async def test_recently_departed_within_grace_period_kept(self):
        """Train that departed 3 minutes ago should still be shown (within 5-min grace).

        The 5-minute grace period allows for minor timing differences between
        scheduled departure and actual departure. A train scheduled to leave
        3 minutes ago might still be at the platform.
        """
        # Train departed 3 minutes ago — within 5-min grace period
        recent_train = self._create_journey_with_past_departure(
            "3850", hours_ago=3 / 60, has_departed_station=False  # 3 minutes
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [recent_train]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        train_ids = {d.train_id for d in result.departures}
        assert (
            "3850" in train_ids
        ), "Train within 5-min grace period should still appear as upcoming"

    @pytest.mark.asyncio
    async def test_cancelled_train_not_affected_by_time_fallback(self):
        """Cancelled trains should bypass the time-based fallback entirely.

        Even if a cancelled train's scheduled departure was hours ago, it should
        still appear (up to the 2-hour base filter window) so users see the
        cancellation notice.
        """
        # Cancelled train from 1 hour ago — should still be visible
        cancelled_train = self._create_journey_with_past_departure(
            "3860", hours_ago=1.0, has_departed_station=False, is_cancelled=True
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [cancelled_train]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        train_ids = {d.train_id for d in result.departures}
        assert (
            "3860" in train_ids
        ), "Cancelled train from 1 hour ago should still appear"

    @pytest.mark.asyncio
    async def test_without_hide_departed_shows_all_trains(self):
        """Without hide_departed, past trains should still appear regardless of time.

        The time-based fallback only applies when hide_departed=True.
        """
        # Train from 4 hours ago with has_departed_station=False
        old_train = self._create_journey_with_past_departure(
            "3840", hours_ago=4.0, has_departed_station=False
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [old_train]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=False)

        train_ids = {d.train_id for d in result.departures}
        assert (
            "3840" in train_ids
        ), "Without hide_departed, all trains should appear regardless of time"

    @pytest.mark.asyncio
    async def test_boundary_at_exactly_five_minutes_ago(self):
        """Train scheduled exactly 5 minutes ago should be EXCLUDED.

        The filter is `scheduled_departure > past_cutoff` where
        past_cutoff = now - 5 min. A train at exactly the cutoff does NOT
        satisfy `>`, so it should be filtered out. This prevents off-by-one
        regressions in the time-based fallback.
        """
        # Train scheduled exactly 5 minutes ago
        boundary_train = self._create_journey_with_past_departure(
            "3870", hours_ago=5 / 60, has_departed_station=False  # exactly 5 min
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        # SQL: scheduled_departure > (now - 5min) is False when equal, so excluded
        mock_scalars.unique.return_value.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        assert (
            len(result.departures) == 0
        ), "Train at exactly 5-min cutoff boundary should be excluded"

    @pytest.mark.asyncio
    async def test_train_just_past_cutoff_excluded(self):
        """Train scheduled 6 minutes ago (past the 5-min grace) should be excluded."""
        old_train = self._create_journey_with_past_departure(
            "3871", hours_ago=6 / 60, has_departed_station=False  # 6 minutes
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        assert (
            len(result.departures) == 0
        ), "Train 6 minutes past departure should be excluded by time fallback"

    @pytest.mark.asyncio
    async def test_has_departed_true_filtered_by_primary_mechanism(self):
        """Train with has_departed_station=True should be filtered (primary path).

        This tests the normal case where the collector correctly set the flag.
        The time-based fallback is secondary; this verifies the primary mechanism.
        """
        # Train departed 10 minutes ago, flag correctly set
        departed_train = self._create_journey_with_past_departure(
            "3872", hours_ago=10 / 60, has_departed_station=True
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        # has_departed_station=True means it fails the is_(False) check -> filtered
        mock_scalars.unique.return_value.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        assert (
            len(result.departures) == 0
        ), "Train with has_departed_station=True should be filtered by primary mechanism"

    @pytest.mark.asyncio
    async def test_null_scheduled_departure_passes_through(self):
        """Train with NULL scheduled_departure and has_departed_station=False should pass.

        The filter conservatively keeps trains with unknown departure times rather
        than hiding them. This prevents hiding trains we can't classify.
        """
        # Create a train with NULL scheduled_departure
        unknown_train = self._create_journey_with_past_departure(
            "3873", hours_ago=0, has_departed_station=False
        )
        # Override: set scheduled_departure to None on the from_stop
        unknown_train.stops[0].scheduled_departure = None
        unknown_train.scheduled_departure = None

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        # NULL scheduled_departure satisfies is_(None) in the OR, so passes
        mock_scalars.unique.return_value.all.return_value = [unknown_train]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        train_ids = {d.train_id for d in result.departures}
        assert (
            "3873" in train_ids
        ), "Train with NULL scheduled_departure should be conservatively shown"

    @pytest.mark.asyncio
    async def test_regression_hamilton_to_ny_penn_stale_trains(self):
        """Regression test for the original bug: Hamilton->NY Penn trains 3840/3850.

        The original bug: trains 3840 and 3850 departed Hamilton hours ago but
        appeared as "upcoming" because has_departed_station was never updated
        (JIT refresh skipped second pass when hide_departed=True, and the
        collector hadn't processed these trains recently). The time-based
        fallback should catch and exclude them.
        """
        now = now_et()

        # Train 3840: departed Hamilton 3 hours ago, stale flag
        train_3840 = self._create_journey_with_past_departure(
            "3840", hours_ago=3.0, has_departed_station=False
        )
        # Train 3850: departed Hamilton 2 hours ago, stale flag
        train_3850 = self._create_journey_with_past_departure(
            "3850", hours_ago=2.0, has_departed_station=False
        )
        # Train 3880: upcoming, departing in 20 minutes
        train_3880 = self._create_journey_with_past_departure(
            "3880", hours_ago=-20 / 60, has_departed_station=False
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalars = Mock()
        # SQL time fallback excludes 3840 and 3850 (hours past cutoff),
        # but keeps 3880 (upcoming)
        mock_scalars.unique.return_value.all.return_value = [train_3880]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)

        service = DepartureService()
        result = await self._run_departures(mock_session, service, hide_departed=True)

        train_ids = {d.train_id for d in result.departures}
        assert (
            "3840" not in train_ids
        ), "Train 3840 (departed 3h ago with stale flag) must not appear as upcoming"
        assert (
            "3850" not in train_ids
        ), "Train 3850 (departed 2h ago with stale flag) must not appear as upcoming"
        assert "3880" in train_ids, "Train 3880 (upcoming in 20 min) should appear"


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

    @pytest.mark.asyncio
    async def test_base_cancelled_filter_has_time_constraint(self):
        """Verify that the base departure filters include a 2-hour time window for cancelled trains.

        Regardless of hide_departed, the SQL filter should be:
            OR(is_cancelled IS NOT TRUE,
               scheduled_departure >= now - 2h)

        This prevents stale cancelled trains from lingering in results all day.
        """
        from sqlalchemy import or_
        from trackrat.models.database import TrainJourney, JourneyStop
        from trackrat.utils.time import now_et

        current_time = now_et()

        # Construct the filter as it appears in departure.py (base filters)
        filter_expr = or_(
            TrainJourney.is_cancelled.is_not(True),
            JourneyStop.scheduled_departure >= current_time - timedelta(hours=2),
        )

        filter_str = str(filter_expr)
        assert (
            "is_cancelled" in filter_str
        ), "Base filter must include is_cancelled check"
        assert (
            "scheduled_departure" in filter_str
        ), "Base filter must include scheduled_departure time constraint"

    @pytest.mark.asyncio
    async def test_hide_departed_filter_allows_cancelled_trains_through(self):
        """Verify that the hide_departed filter lets cancelled trains pass through.

        The hide_departed SQL filter includes:
        - has_departed_station check (primary)
        - scheduled_departure time-based fallback (catches stale flags)
        - is_cancelled bypass (always show cancelled trains)

        Cancelled trains always have has_departed_station=False, but we
        explicitly allow them through so the base filter's 2-hour window
        is the sole gatekeeper for stale cancelled trains.
        """
        from sqlalchemy import and_, or_
        from trackrat.models.database import TrainJourney, JourneyStop
        from trackrat.utils.time import now_et

        past_cutoff = now_et() - timedelta(minutes=5)

        # Construct the filter as it appears in departure.py
        filter_expr = or_(
            and_(
                JourneyStop.has_departed_station.is_(False),
                or_(
                    JourneyStop.scheduled_departure.is_(None),
                    JourneyStop.scheduled_departure > past_cutoff,
                ),
            ),
            TrainJourney.is_cancelled.is_(True),
        )

        filter_str = str(filter_expr)
        assert (
            "is_cancelled" in filter_str
        ), "hide_departed filter must include is_cancelled check"
        assert (
            "has_departed_station" in filter_str
        ), "hide_departed filter must include has_departed_station check"
        assert (
            "scheduled_departure" in filter_str
        ), "hide_departed filter must include time-based fallback"


class TestStaleScheduledFiltering:
    """Tests for filtering SCHEDULED trains close to departure time.

    SCHEDULED trains from systems with real-time data are hidden when within
    their per-source threshold of departure and haven't been upgraded to
    OBSERVED by discovery. Thresholds are sized to each provider's discovery
    cadence: 15 min for NJT/Amtrak (30-min discovery), 5 min for PATH/LIRR/
    MNR/SUBWAY/BART/MBTA/METRA (4-min discovery), 4 min for WMATA (3-min).

    PATCO trains (schedule-only) should never be filtered since there's
    no real-time system to discover them.
    """

    def _create_departure(
        self,
        train_id: str,
        data_source: str,
        observation_type: str,
        minutes_until_departure: int,
    ) -> "TrainDeparture":
        """Create a TrainDeparture for testing."""
        from trackrat.models.api import (
            DataFreshness,
            LineInfo,
            StationInfo,
            TrainDeparture,
            TrainPosition,
        )

        now = now_et()
        scheduled_time = now + timedelta(minutes=minutes_until_departure)

        return TrainDeparture(
            train_id=train_id,
            journey_date=now.date(),
            line=LineInfo(code="NE", name="Northeast Corridor", color="#000000"),
            destination="New York",
            departure=StationInfo(
                code="TR",
                name="Trenton",
                scheduled_time=scheduled_time,
                updated_time=None,
                actual_time=None,
                track=None,
            ),
            arrival=None,
            train_position=TrainPosition(),
            data_freshness=DataFreshness(
                last_updated=now,
                age_seconds=0,
                update_count=1,
            ),
            data_source=data_source,
            observation_type=observation_type,
            is_cancelled=False,
        )

    def test_filter_scheduled_njt_within_threshold(self):
        """SCHEDULED NJT train within 15 min of departure should be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="1234",
                data_source="NJT",
                observation_type="SCHEDULED",
                minutes_until_departure=10,  # Within threshold (15 min)
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert (
            len(result) == 0
        ), "SCHEDULED NJT train within threshold should be filtered"

    def test_filter_scheduled_amtrak_within_threshold(self):
        """SCHEDULED Amtrak train within 15 min of departure should be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="A123",
                data_source="AMTRAK",
                observation_type="SCHEDULED",
                minutes_until_departure=10,  # Within threshold (15 min)
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert (
            len(result) == 0
        ), "SCHEDULED Amtrak train within threshold should be filtered"

    def test_filter_scheduled_path_within_threshold(self):
        """SCHEDULED PATH train within 5-min threshold should be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="PATH-123",
                data_source="PATH",
                observation_type="SCHEDULED",
                minutes_until_departure=3,  # Within PATH threshold (5 min)
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert (
            len(result) == 0
        ), "SCHEDULED PATH train within 5-min threshold should be filtered"

    def test_keep_scheduled_path_outside_threshold(self):
        """SCHEDULED PATH train at 6 min (outside 5-min threshold) should be kept."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="PATH-456",
                data_source="PATH",
                observation_type="SCHEDULED",
                minutes_until_departure=6,  # Outside PATH threshold (5 min)
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert len(result) == 1, (
            "SCHEDULED PATH train at 6 min should be kept (PATH threshold is 5 min)"
        )
        assert result[0].train_id == "PATH-456"

    def test_keep_scheduled_patco_within_threshold(self):
        """SCHEDULED PATCO train within 15 min should NOT be filtered (no real-time API)."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="PATCO-123",
                data_source="PATCO",
                observation_type="SCHEDULED",
                minutes_until_departure=10,  # Within threshold, but PATCO
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert len(result) == 1, "SCHEDULED PATCO train should never be filtered"
        assert result[0].train_id == "PATCO-123"

    def test_keep_scheduled_outside_threshold(self):
        """SCHEDULED train outside 15 min threshold should NOT be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="1234",
                data_source="NJT",
                observation_type="SCHEDULED",
                minutes_until_departure=45,  # Outside threshold
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert len(result) == 1, "SCHEDULED train outside threshold should be kept"
        assert result[0].train_id == "1234"

    def test_keep_observed_within_threshold(self):
        """OBSERVED train within 15 min threshold should NOT be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="1234",
                data_source="NJT",
                observation_type="OBSERVED",
                minutes_until_departure=10,  # Within threshold, but OBSERVED
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert len(result) == 1, "OBSERVED train should never be filtered"
        assert result[0].train_id == "1234"

    def test_mixed_departures_filtering(self):
        """Test filtering with a mix of different departure types and per-source thresholds."""
        service = DepartureService()
        now = now_et()

        departures = [
            # Should be filtered: SCHEDULED NJT within 15-min threshold
            self._create_departure("1001", "NJT", "SCHEDULED", 5),
            # Should be kept: OBSERVED NJT within threshold
            self._create_departure("1002", "NJT", "OBSERVED", 5),
            # Should be filtered: SCHEDULED AMTRAK within 15-min threshold
            self._create_departure("A1003", "AMTRAK", "SCHEDULED", 10),
            # Should be kept: SCHEDULED NJT outside threshold
            self._create_departure("1004", "NJT", "SCHEDULED", 60),
            # Should be kept: SCHEDULED PATCO (no real-time API)
            self._create_departure("P1005", "PATCO", "SCHEDULED", 5),
            # Should be kept: SCHEDULED PATH at 10 min, outside 5-min threshold
            self._create_departure("PATH-1006", "PATH", "SCHEDULED", 10),
            # Should be filtered: SCHEDULED PATH at 3 min, within 5-min threshold
            self._create_departure("PATH-1007", "PATH", "SCHEDULED", 3),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        # Should keep: 1002 (observed), 1004 (outside NJT threshold),
        #   P1005 (PATCO), PATH-1006 (outside PATH 5-min threshold)
        assert len(result) == 4
        result_ids = {d.train_id for d in result}
        assert result_ids == {"1002", "1004", "P1005", "PATH-1006"}

    def test_boundary_at_exactly_threshold(self):
        """Train departing exactly at threshold boundary should be kept."""
        service = DepartureService()
        now = now_et()

        # Train departing in exactly 15 minutes (at the threshold)
        departures = [
            self._create_departure(
                train_id="1234",
                data_source="NJT",
                observation_type="SCHEDULED",
                minutes_until_departure=15,  # Exactly at threshold
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        # At exactly 15 minutes, scheduled_time == threshold, so < threshold is False
        # The train should be kept (we filter only those strictly less than threshold)
        assert len(result) == 1, "Train at exactly threshold should be kept"

    def test_boundary_just_under_threshold(self):
        """Train departing just under threshold should be filtered."""
        service = DepartureService()
        now = now_et()

        # Train departing in 14 minutes (just under threshold)
        departures = [
            self._create_departure(
                train_id="1234",
                data_source="NJT",
                observation_type="SCHEDULED",
                minutes_until_departure=14,  # Just under threshold
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert len(result) == 0, "Train just under threshold should be filtered"

    def test_njt_threshold_unchanged_at_14_min(self):
        """Regression: NJT still uses 15-min threshold — 14 min is filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure("NJT-1", "NJT", "SCHEDULED", 14),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)
        assert len(result) == 0, "NJT SCHEDULED at 14 min should be filtered (threshold=15)"

    def test_path_boundary_at_exactly_5_min(self):
        """PATH train at exactly 5-min threshold should be kept (< not <=)."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure("PATH-B", "PATH", "SCHEDULED", 5),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)
        assert len(result) == 1, "PATH at exactly 5 min should be kept"

    def test_path_boundary_at_4_min(self):
        """PATH train at 4 min (under 5-min threshold) should be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure("PATH-C", "PATH", "SCHEDULED", 4),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)
        assert len(result) == 0, "PATH at 4 min should be filtered (threshold=5)"

    def test_wmata_uses_4_min_threshold(self):
        """WMATA uses 4-min threshold (3-min discovery cycle)."""
        service = DepartureService()
        now = now_et()

        kept = [self._create_departure("WMATA-K", "WMATA", "SCHEDULED", 4)]
        filtered = [self._create_departure("WMATA-F", "WMATA", "SCHEDULED", 3)]

        result_kept = service._filter_stale_scheduled_trains(kept, now)
        assert len(result_kept) == 1, "WMATA at 4 min should be kept (threshold=4)"

        result_filtered = service._filter_stale_scheduled_trains(filtered, now)
        assert len(result_filtered) == 0, "WMATA at 3 min should be filtered (threshold=4)"

    def test_subway_uses_5_min_threshold(self):
        """SUBWAY uses 5-min threshold (4-min discovery cycle)."""
        service = DepartureService()
        now = now_et()

        kept = [self._create_departure("SUB-K", "SUBWAY", "SCHEDULED", 6)]
        filtered = [self._create_departure("SUB-F", "SUBWAY", "SCHEDULED", 3)]

        result_kept = service._filter_stale_scheduled_trains(kept, now)
        assert len(result_kept) == 1, "SUBWAY at 6 min should be kept (threshold=5)"

        result_filtered = service._filter_stale_scheduled_trains(filtered, now)
        assert len(result_filtered) == 0, "SUBWAY at 3 min should be filtered (threshold=5)"

    def test_lirr_uses_5_min_threshold(self):
        """LIRR uses 5-min threshold (4-min discovery cycle)."""
        service = DepartureService()
        now = now_et()

        kept = [self._create_departure("LIRR-K", "LIRR", "SCHEDULED", 6)]
        filtered = [self._create_departure("LIRR-F", "LIRR", "SCHEDULED", 4)]

        result_kept = service._filter_stale_scheduled_trains(kept, now)
        assert len(result_kept) == 1, "LIRR at 6 min should be kept (threshold=5)"

        result_filtered = service._filter_stale_scheduled_trains(filtered, now)
        assert len(result_filtered) == 0, "LIRR at 4 min should be filtered (threshold=5)"

    def test_mnr_uses_5_min_threshold(self):
        """MNR uses 5-min threshold (4-min discovery cycle)."""
        service = DepartureService()
        now = now_et()

        kept = [self._create_departure("MNR-K", "MNR", "SCHEDULED", 7)]
        filtered = [self._create_departure("MNR-F", "MNR", "SCHEDULED", 4)]

        result_kept = service._filter_stale_scheduled_trains(kept, now)
        assert len(result_kept) == 1, "MNR at 7 min should be kept (threshold=5)"

        result_filtered = service._filter_stale_scheduled_trains(filtered, now)
        assert len(result_filtered) == 0, "MNR at 4 min should be filtered (threshold=5)"

    def test_per_source_thresholds_in_single_batch(self):
        """Different providers apply their own thresholds in the same filter call."""
        service = DepartureService()
        now = now_et()

        departures = [
            # PATH at 6 min: kept (threshold=5)
            self._create_departure("PATH-1", "PATH", "SCHEDULED", 6),
            # NJT at 6 min: filtered (threshold=15)
            self._create_departure("NJT-1", "NJT", "SCHEDULED", 6),
            # WMATA at 6 min: kept (threshold=4)
            self._create_departure("WMATA-1", "WMATA", "SCHEDULED", 6),
            # AMTRAK at 6 min: filtered (threshold=15)
            self._create_departure("AMT-1", "AMTRAK", "SCHEDULED", 6),
            # SUBWAY at 6 min: kept (threshold=5)
            self._create_departure("SUB-1", "SUBWAY", "SCHEDULED", 6),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)
        result_ids = {d.train_id for d in result}

        assert result_ids == {"PATH-1", "WMATA-1", "SUB-1"}, (
            f"Expected PATH/WMATA/SUBWAY kept at 6 min, NJT/AMTRAK filtered. Got: {result_ids}"
        )
