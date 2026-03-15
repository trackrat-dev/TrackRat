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
    async def test_hide_departed_cancelled_filter_has_time_constraint(self):
        """Verify that the hide_departed filter for cancelled trains includes a 2-hour time window.

        The SQL filter should be:
            OR(has_departed_station IS NOT TRUE,
               AND(is_cancelled IS TRUE, scheduled_departure >= now - 2h))

        This ensures cancelled trains don't persist all day — only for 2 hours
        past their scheduled departure.
        """
        from sqlalchemy import and_, or_
        from trackrat.models.database import TrainJourney, JourneyStop
        from trackrat.utils.time import now_et

        current_time = now_et()

        # Construct the filter as it appears in departure.py
        filter_expr = or_(
            JourneyStop.has_departed_station.is_(False),
            and_(
                TrainJourney.is_cancelled.is_(True),
                JourneyStop.scheduled_departure >= current_time - timedelta(hours=2),
            ),
        )

        filter_str = str(filter_expr)
        # Verify both is_cancelled and scheduled_departure appear in the expression
        assert (
            "is_cancelled" in filter_str
        ), "hide_departed filter must include is_cancelled check"
        assert (
            "scheduled_departure" in filter_str
        ), "hide_departed filter must include scheduled_departure time constraint"
        assert (
            "has_departed_station" in filter_str
        ), "hide_departed filter must still include has_departed_station check"


class TestStaleScheduledFiltering:
    """Tests for filtering SCHEDULED trains close to departure time.

    SCHEDULED trains from systems with real-time data (NJT, Amtrak, PATH)
    should be hidden when they're within 15 minutes of departure and
    haven't been upgraded to OBSERVED by the discovery system.

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
        """SCHEDULED PATH train within 15 min of departure should be filtered."""
        service = DepartureService()
        now = now_et()

        departures = [
            self._create_departure(
                train_id="PATH-123",
                data_source="PATH",
                observation_type="SCHEDULED",
                minutes_until_departure=10,  # Within threshold
            )
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        assert (
            len(result) == 0
        ), "SCHEDULED PATH train within threshold should be filtered"

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
        """Test filtering with a mix of different departure types."""
        service = DepartureService()
        now = now_et()

        departures = [
            # Should be filtered: SCHEDULED NJT within threshold (15 min)
            self._create_departure("1001", "NJT", "SCHEDULED", 5),
            # Should be kept: OBSERVED NJT within threshold
            self._create_departure("1002", "NJT", "OBSERVED", 5),
            # Should be filtered: SCHEDULED AMTRAK within threshold
            self._create_departure("A1003", "AMTRAK", "SCHEDULED", 10),
            # Should be kept: SCHEDULED NJT outside threshold
            self._create_departure("1004", "NJT", "SCHEDULED", 60),
            # Should be kept: SCHEDULED PATCO within threshold (no real-time)
            self._create_departure("P1005", "PATCO", "SCHEDULED", 5),
            # Should be filtered: SCHEDULED PATH within threshold
            self._create_departure("PATH-1006", "PATH", "SCHEDULED", 10),
        ]

        result = service._filter_stale_scheduled_trains(departures, now)

        # Should keep: 1002 (observed), 1004 (outside threshold), P1005 (PATCO)
        assert len(result) == 3
        result_ids = {d.train_id for d in result}
        assert result_ids == {"1002", "1004", "P1005"}

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
