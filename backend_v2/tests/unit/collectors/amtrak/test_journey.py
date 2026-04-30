"""
Unit tests for Amtrak journey collector.

Tests the journey collection logic for Amtrak trains.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.amtrak import create_amtrak_station_data, create_amtrak_train_data
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.database import TrainJourney
from trackrat.utils.time import ET


@pytest.fixture
def journey_collector():
    """Create an AmtrakJourneyCollector instance."""
    return AmtrakJourneyCollector()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def sample_train_data():
    """Create sample Amtrak train data."""
    return create_amtrak_train_data(
        train_id="2150-4",
        train_num="2150",
        route="Northeast Regional",
        train_state="Active",
        stations=[
            create_amtrak_station_data(
                code="NYP",
                name="New York Penn Station",
                sch_dep="2025-07-05T14:30:00-05:00",
                status="Departed",
                platform="15",
            ),
            create_amtrak_station_data(
                code="NWK",
                name="Newark Penn Station",
                sch_arr="2025-07-05T14:45:00-05:00",
                sch_dep="2025-07-05T14:47:00-05:00",
                status="Enroute",
            ),
            create_amtrak_station_data(
                code="TRE",
                name="Trenton",
                sch_arr="2025-07-05T15:15:00-05:00",
                sch_dep="2025-07-05T15:17:00-05:00",
                status="Enroute",
            ),
            create_amtrak_station_data(
                code="PHL",  # Philadelphia - now tracked
                name="Philadelphia",
                sch_arr="2025-07-05T15:45:00-05:00",
                sch_dep="2025-07-05T15:50:00-05:00",
                status="Enroute",
            ),
        ],
    )


class TestAmtrakJourneyCollector:
    """Test suite for AmtrakJourneyCollector."""

    def test_init(self, journey_collector):
        """Test collector initialization."""
        assert journey_collector.client is not None
        assert hasattr(journey_collector, "STATUS_MAP")
        assert hasattr(journey_collector, "TRAIN_STATE_MAP")

    def test_status_mappings(self, journey_collector):
        """Test status mapping dictionaries."""
        # Test STATUS_MAP
        assert journey_collector.STATUS_MAP["Departed"] == "DEPARTED"
        assert journey_collector.STATUS_MAP["Station"] == "BOARDING"
        assert journey_collector.STATUS_MAP["Enroute"] == "EN ROUTE"
        assert journey_collector.STATUS_MAP["Cancelled"] == "CANCELLED"
        assert journey_collector.STATUS_MAP["Terminated"] == "DEPARTED"
        assert journey_collector.STATUS_MAP["Predeparture"] == "BOARDING"

        # Test TRAIN_STATE_MAP
        assert journey_collector.TRAIN_STATE_MAP["Active"] == "EN ROUTE"
        assert journey_collector.TRAIN_STATE_MAP["Predeparture"] == "BOARDING"
        assert journey_collector.TRAIN_STATE_MAP["Terminated"] == "DEPARTED"

    @pytest.mark.asyncio
    async def test_collect_journey_success(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test successful journey collection."""
        train_id = "2150-4"

        # Mock the _get_train_data method
        with patch.object(journey_collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = sample_train_data

            # Mock the _convert_to_journey method
            with patch.object(journey_collector, "_convert_to_journey") as mock_convert:
                mock_journey = Mock(spec=TrainJourney)
                mock_journey.train_id = "A2150"
                mock_journey.stops = []
                mock_convert.return_value = mock_journey

                # Mock get_session to return our mock session
                with patch(
                    "trackrat.collectors.amtrak.journey.get_session"
                ) as mock_get_session:
                    mock_get_session.return_value.__aenter__.return_value = (
                        mock_db_session
                    )

                    result = await journey_collector.collect_journey(train_id)

                    # Verify the journey was processed
                    assert result == mock_journey
                    mock_get_train_data.assert_called_once_with(train_id)
                    mock_convert.assert_called_once_with(
                        mock_db_session, sample_train_data
                    )
                    # Note: commit is handled by the session context manager
                    # and may not be visible in this mock setup

    @pytest.mark.asyncio
    async def test_collect_journey_train_not_found(
        self, journey_collector, mock_db_session
    ):
        """Test journey collection when train is not found."""
        train_id = "NONEXISTENT"

        with patch.object(journey_collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = None

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = mock_db_session

                result = await journey_collector.collect_journey(train_id)

                assert result is None
                mock_get_train_data.assert_called_once_with(train_id)
                mock_db_session.add.assert_not_called()
                mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_conversion_failure(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test journey collection when conversion fails."""
        train_id = "2150-4"

        with patch.object(journey_collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = sample_train_data

            with patch.object(journey_collector, "_convert_to_journey") as mock_convert:
                mock_convert.return_value = None

                with patch(
                    "trackrat.collectors.amtrak.journey.get_session"
                ) as mock_get_session:
                    mock_get_session.return_value.__aenter__.return_value = (
                        mock_db_session
                    )

                    result = await journey_collector.collect_journey(train_id)

                    assert result is None
                    mock_db_session.add.assert_not_called()
                    mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_database_error(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test journey collection with database error."""
        train_id = "2150-4"

        with patch.object(journey_collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = sample_train_data

            with patch.object(journey_collector, "_convert_to_journey") as mock_convert:
                # Make _convert_to_journey raise a non-retryable exception
                mock_convert.side_effect = Exception("Connection pool exhausted")

                with patch(
                    "trackrat.collectors.amtrak.journey.get_session"
                ) as mock_get_session:
                    mock_get_session.return_value.__aenter__.return_value = (
                        mock_db_session
                    )

                    # With retry decorator, non-retryable exceptions are re-raised
                    with pytest.raises(Exception, match="Connection pool exhausted"):
                        await journey_collector.collect_journey(train_id)

    @pytest.mark.asyncio
    async def test_collect_journey_database_busy_error_retries(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test journey collection with database busy error that succeeds after retry."""
        train_id = "2150-4"

        with patch.object(journey_collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = sample_train_data

            with patch.object(journey_collector, "_convert_to_journey") as mock_convert:
                mock_journey = Mock(spec=TrainJourney)

                # Make _convert_to_journey fail once with busy error, then succeed
                mock_convert.side_effect = [
                    Exception(
                        "deadlock detected"
                    ),  # First attempt fails (PostgreSQL error)
                    mock_journey,  # Second attempt succeeds
                ]

                with patch(
                    "trackrat.collectors.amtrak.journey.get_session"
                ) as mock_get_session:
                    mock_get_session.return_value.__aenter__.return_value = (
                        mock_db_session
                    )

                    with patch("asyncio.sleep") as mock_sleep:
                        result = await journey_collector.collect_journey(train_id)

                        # Should succeed after retry
                        assert result == mock_journey
                        # Should have slept once for the retry
                        assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    async def test_run_method(self, journey_collector):
        """Test the run method returns empty results."""
        result = await journey_collector.run()

        assert result == {
            "trains_processed": 0,
            "successful": 0,
            "failed": 0,
            "data_source": "AMTRAK",
        }

    @pytest.mark.asyncio
    async def test_get_train_data_found(self, journey_collector, sample_train_data):
        """Test _get_train_data when train is found."""
        train_id = "2150-4"

        # Mock the client's get_all_trains method
        mock_client = AsyncMock()
        mock_client.get_all_trains.return_value = {
            "station1": [sample_train_data],
            "station2": [create_amtrak_train_data(train_id="OTHER", train_num="OTHER")],
        }

        with patch.object(journey_collector, "client", mock_client):
            result = await journey_collector._get_train_data(train_id)

            assert result == sample_train_data
            mock_client.__aenter__.assert_called_once()
            mock_client.get_all_trains.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_train_data_not_found(self, journey_collector):
        """Test _get_train_data when train is not found."""
        train_id = "NONEXISTENT"

        # Mock the client's get_all_trains method
        mock_client = AsyncMock()
        mock_client.get_all_trains.return_value = {
            "station1": [create_amtrak_train_data(train_id="OTHER", train_num="OTHER")]
        }

        with patch.object(journey_collector, "client", mock_client):
            result = await journey_collector._get_train_data(train_id)

            assert result is None
            mock_client.__aenter__.assert_called_once()
            mock_client.get_all_trains.assert_called_once()

    def test_parse_amtrak_time_success(self, journey_collector):
        """Test _parse_amtrak_time with valid time strings."""
        # Test ISO format with timezone
        time_str = "2025-07-05T14:30:00-05:00"
        result = journey_collector._parse_amtrak_time(time_str)

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_amtrak_time_with_z_suffix(self, journey_collector):
        """Test _parse_amtrak_time with Z suffix."""
        time_str = "2025-07-05T14:30:00Z"
        result = journey_collector._parse_amtrak_time(time_str)

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_amtrak_time_invalid(self, journey_collector):
        """Test _parse_amtrak_time with invalid time string."""
        time_str = "invalid-time"
        result = journey_collector._parse_amtrak_time(time_str)

        assert result is None

    @pytest.mark.asyncio
    async def test_convert_to_journey_new_journey(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test _convert_to_journey for a new journey."""
        # Mock the session query to return no existing journey
        mock_db_session.scalar.return_value = None

        # Mock flush and refresh to do nothing
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Mock time functions
        with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

            result = await journey_collector._convert_to_journey(
                mock_db_session, sample_train_data
            )

            assert result is not None
            assert isinstance(result, TrainJourney)
            assert result.train_id == "A2150"
            assert result.data_source == "AMTRAK"
            assert result.line_code == "AM"
            assert result.line_name == "Amtrak"
            assert result.destination == "Washington Union Station"
            assert result.stops_count == 4  # Only tracked stations (NYP, NWK, TRE, PHL)
            assert result.has_complete_journey is True
            # Verify correct number of session.add calls:
            # 1 journey + 4 stops + 1 snapshot = 6 total
            assert mock_db_session.add.call_count == 6
            # Verify flush and refresh were called
            mock_db_session.flush.assert_called()
            mock_db_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_convert_to_journey_existing_journey(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """Test _convert_to_journey for an existing journey."""
        # Mock existing journey
        existing_journey = Mock(spec=TrainJourney)
        existing_journey.id = 1
        existing_journey.stops = []
        existing_journey.snapshots = []
        existing_journey.update_count = 5
        existing_journey.observation_type = "SCHEDULED"
        mock_db_session.scalar.return_value = existing_journey

        # Mock flush, refresh, and execute to do nothing
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        mock_db_session.execute = AsyncMock()

        # Mock time functions
        with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
            mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

            result = await journey_collector._convert_to_journey(
                mock_db_session, sample_train_data
            )

            assert result == existing_journey
            assert result.update_count == 6  # Should increment
            # Verify flush and refresh were called
            mock_db_session.flush.assert_called()
            mock_db_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_convert_to_journey_no_tracked_origin(
        self, journey_collector, mock_db_session
    ):
        """Test _convert_to_journey when no tracked origin station is found."""
        # Create train data with no tracked stations
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="XYZ",  # Non-existent station code - not tracked
                    name="Fake Station",
                    sch_dep="2025-07-05T14:30:00-05:00",
                    status="Departed",
                )
            ],
        )

        result = await journey_collector._convert_to_journey(
            mock_db_session, train_data
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_convert_to_journey_conversion_error(
        self, journey_collector, mock_db_session
    ):
        """Test _convert_to_journey when conversion fails with exception."""
        # Create invalid train data that will cause an error
        train_data = Mock()
        train_data.trainNum = None  # This will cause an error

        result = await journey_collector._convert_to_journey(
            mock_db_session, train_data
        )

        assert result is None

    def test_convert_to_journey_cancelled_train(
        self, journey_collector, sample_train_data
    ):
        """Test journey conversion for cancelled train."""
        sample_train_data.trainState = "Cancelled"

        # We can't easily test the full conversion without a lot of mocking,
        # but we can verify the status mapping logic
        assert (
            journey_collector.TRAIN_STATE_MAP.get("Cancelled", "UNKNOWN") == "UNKNOWN"
        )

    def test_convert_to_journey_terminated_train(
        self, journey_collector, sample_train_data
    ):
        """Test journey conversion for terminated train."""
        sample_train_data.trainState = "Terminated"

        # Verify the status mapping
        assert journey_collector.TRAIN_STATE_MAP.get("Terminated") == "DEPARTED"

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("Departed", "DEPARTED"),
            ("Station", "BOARDING"),
            ("Enroute", "EN ROUTE"),
            ("Cancelled", "CANCELLED"),
            ("Terminated", "DEPARTED"),
            ("Predeparture", "BOARDING"),
            ("Unknown", "Unknown"),  # Unmapped status should pass through
        ],
    )
    def test_status_mapping_parametrized(self, journey_collector, status, expected):
        """Test status mapping with various inputs."""
        result = journey_collector.STATUS_MAP.get(status, status)
        assert result == expected

    @pytest.mark.parametrize(
        "train_state,expected",
        [
            ("Active", "EN ROUTE"),
            ("Predeparture", "BOARDING"),
            ("Terminated", "DEPARTED"),
            ("Unknown", "UNKNOWN"),  # Unmapped state should use default
        ],
    )
    def test_train_state_mapping_parametrized(
        self, journey_collector, train_state, expected
    ):
        """Test train state mapping with various inputs."""
        result = journey_collector.TRAIN_STATE_MAP.get(train_state, "UNKNOWN")
        assert result == expected


class TestComputeEstimatedTime:
    """Tests for _compute_estimated_time delay comment parsing."""

    SCHEDULED = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

    @pytest.mark.parametrize(
        "comment,expected_offset_min,description",
        [
            ("5 Min Late", 5, "standard delay format"),
            ("64 Min Late", 64, "large delay"),
            ("1 min late", 1, "lowercase format"),
            ("120 MIN LATE", 120, "uppercase format"),
            ("5  min  late", 5, "extra whitespace"),
            ("10 Min Early", -10, "early arrival"),
            ("3 min early", -3, "lowercase early"),
        ],
    )
    def test_delay_comments(self, comment, expected_offset_min, description):
        """Test that delay/early comments correctly shift the scheduled time.

        Validates: {description}
        """
        from datetime import timedelta

        result = AmtrakJourneyCollector._compute_estimated_time(self.SCHEDULED, comment)
        expected = self.SCHEDULED + timedelta(minutes=expected_offset_min)
        assert (
            result == expected
        ), f"comment={comment!r}: expected {expected}, got {result}"

    @pytest.mark.parametrize(
        "comment,description",
        [
            ("On Time", "on-time returns scheduled"),
            ("Cancelled", "cancelled returns scheduled"),
            ("", "empty string returns scheduled"),
            ("Next Stop", "unrecognized comment returns scheduled"),
        ],
    )
    def test_no_shift_comments(self, comment, description):
        """Test that non-delay comments return scheduled time unchanged.

        Validates: {description}
        """
        result = AmtrakJourneyCollector._compute_estimated_time(self.SCHEDULED, comment)
        assert (
            result == self.SCHEDULED
        ), f"comment={comment!r}: expected scheduled time unchanged, got {result}"

    def test_none_scheduled_returns_none(self):
        """Test that None scheduled time returns None regardless of comment."""
        result = AmtrakJourneyCollector._compute_estimated_time(None, "5 Min Late")
        assert result is None

    def test_none_scheduled_empty_comment_returns_none(self):
        """Test that None scheduled with empty comment returns None."""
        result = AmtrakJourneyCollector._compute_estimated_time(None, "")
        assert result is None


class TestAmtrakOrphanStopRemoval:
    """Verifies that stops absent from the live API response are deleted.

    Regression test for the case where the pattern scheduler creates a
    SCHEDULED journey by copying stops from a prior OBSERVED journey, and
    those stops include stations the train no longer stops at on this run
    (e.g., Acela 2107 with a stale Metropark stop). Without cleanup, the
    stale stop persists with wrong times after SCHEDULED -> OBSERVED.
    """

    @pytest.mark.asyncio
    async def test_convert_removes_stops_not_in_api(self, db_session):
        """SCHEDULED journey with stale MP stop drops it on first observation."""
        from sqlalchemy import select

        from trackrat.models.database import JourneyStop

        journey_collector = AmtrakJourneyCollector()

        # Seed a SCHEDULED journey that includes a stale Metropark stop.
        # Mirrors what AmtrakPatternScheduler creates from past observations.
        sched_dep_ny = ET.localize(datetime(2026, 4, 30, 7, 35, 0))
        stale_mp_arrival = ET.localize(datetime(2026, 4, 30, 6, 56, 0))

        journey = TrainJourney(
            train_id="2107",
            journey_date=date(2026, 4, 30),
            data_source="AMTRAK",
            observation_type="SCHEDULED",
            line_code="AM",
            line_name="Amtrak",
            origin_station_code="NY",
            terminal_station_code="WS",
            destination="Washington Union",
            scheduled_departure=sched_dep_ny,
            has_complete_journey=False,
            stops_count=3,
            update_count=1,
        )
        db_session.add(journey)
        await db_session.flush()

        for seq, code, name, sched in [
            (0, "NY", "New York Penn Station", sched_dep_ny),
            (
                1,
                "MP",
                "Metropark",
                stale_mp_arrival,
            ),  # The stale stop the API never returns
            (
                2,
                "PH",
                "Philadelphia",
                ET.localize(datetime(2026, 4, 30, 8, 41, 0)),
            ),
        ]:
            db_session.add(
                JourneyStop(
                    journey_id=journey.id,
                    station_code=code,
                    station_name=name,
                    stop_sequence=seq,
                    scheduled_arrival=sched,
                    scheduled_departure=sched,
                    has_departed_station=False,
                )
            )
        await db_session.flush()

        # Now mimic the live API response for Acela 2107: NYP, NWK, PHL, WAS.
        # No Metropark — Acelas don't stop there.
        train_data = create_amtrak_train_data(
            train_id="2107-30",
            train_num="2107",
            route="Acela",
            train_state="Predeparture",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn",
                    sch_arr="2026-04-30T07:35:00-04:00",
                    sch_dep="2026-04-30T07:35:00-04:00",
                    actual_arr="2026-04-30T07:35:00-04:00",
                    actual_dep="2026-04-30T07:35:00-04:00",
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="NWK",
                    name="Newark Penn",
                    sch_arr="2026-04-30T07:49:00-04:00",
                    sch_dep="2026-04-30T07:50:00-04:00",
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="PHL",
                    name="Philadelphia",
                    sch_arr="2026-04-30T08:41:00-04:00",
                    sch_dep="2026-04-30T08:43:00-04:00",
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="WAS",
                    name="Washington Union",
                    sch_arr="2026-04-30T10:30:00-04:00",
                    sch_dep="2026-04-30T10:30:00-04:00",
                    status="Enroute",
                ),
            ],
        )

        result = await journey_collector._convert_to_journey(db_session, train_data)
        await db_session.flush()

        assert result is not None
        assert result.observation_type == "OBSERVED"

        # Verify the surviving stops are exactly the stations from the API,
        # with sequential indices and no stale Metropark.
        stops = (
            (
                await db_session.execute(
                    select(JourneyStop)
                    .where(JourneyStop.journey_id == result.id)
                    .order_by(JourneyStop.stop_sequence)
                )
            )
            .scalars()
            .all()
        )

        codes = [s.station_code for s in stops]
        assert (
            "MP" not in codes
        ), f"Stale Metropark stop should have been deleted; got {codes}"
        assert codes == ["NY", "NP", "PH", "WS"]

        # Ensure stop_sequence is contiguous (no gaps from deleted stops)
        assert [s.stop_sequence for s in stops] == [0, 1, 2, 3]
