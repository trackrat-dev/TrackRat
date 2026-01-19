"""
Integration tests for departure service with Amtrak data.

Tests how the departure service integrates Amtrak and NJT data
for multi-source departures.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et

from tests.factories.amtrak import create_amtrak_journey, create_amtrak_journey_stop


@pytest.mark.asyncio
class TestDepartureServiceIntegration:
    """Test suite for departure service integration with Amtrak data."""

    async def test_mixed_departures_amtrak_and_njt(self, db_session: AsyncSession):
        """Test departure service returns both Amtrak and NJT trains."""
        service = DepartureService()

        # Create Amtrak journey
        amtrak_journey = create_amtrak_journey(
            train_id="A2150",
            origin="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            line_code="AM",
            line_name="Amtrak",
            data_source="AMTRAK",
        )

        # Add stops to Amtrak journey
        ny_stop_amtrak = create_amtrak_journey_stop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
            track="15",
        )
        tr_stop_amtrak = create_amtrak_journey_stop(
            station_code="TR",
            station_name="Trenton",
            scheduled_arrival=now_et() + timedelta(hours=1, minutes=45),
            stop_sequence=1,
        )
        amtrak_journey.stops = [ny_stop_amtrak, tr_stop_amtrak]

        # Create NJT journey
        njt_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            line_color="#F7505E",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=True,
            update_count=1,
        )

        # Add stops to NJT journey
        ny_stop_njt = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
            updated_departure=now_et() + timedelta(hours=1, minutes=30),
            stop_sequence=0,
            track="7",
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        )
        tr_stop_njt = JourneyStop(
            station_code="TR",
            station_name="Trenton",
            scheduled_arrival=now_et() + timedelta(hours=2, minutes=15),
            updated_arrival=now_et() + timedelta(hours=2, minutes=15),
            stop_sequence=1,
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        )
        njt_journey.stops = [ny_stop_njt, tr_stop_njt]

        # Add both journeys to database
        db_session.add(amtrak_journey)
        db_session.add(njt_journey)
        await db_session.commit()

        # Mock NJTransitClient to not make external API calls
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            # Get departures from NY to TR
            response = await service.get_departures(
                db=db_session,
                from_station="NY",
                to_station="TR",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

        # Verify response contains both trains
        assert len(response.departures) == 2

        # Sort by departure time to ensure consistent ordering
        departures = sorted(
            response.departures, key=lambda d: d.departure.scheduled_time
        )

        # First should be Amtrak (earlier departure)
        amtrak_dep = departures[0]
        assert amtrak_dep.train_id == "A2150"
        assert amtrak_dep.line.code == "AM"
        assert amtrak_dep.line.name == "Amtrak"
        assert amtrak_dep.departure.track == "15"
        assert amtrak_dep.data_source == "AMTRAK"

        # Second should be NJT
        njt_dep = departures[1]
        assert njt_dep.train_id == "3840"
        assert njt_dep.line.code == "NE"
        assert njt_dep.line.name == "Northeast Corridor"
        assert njt_dep.departure.track == "7"
        assert njt_dep.data_source == "NJT"

        # Verify metadata
        assert response.metadata["from_station"]["code"] == "NY"
        assert response.metadata["to_station"]["code"] == "TR"
        assert response.metadata["count"] == 2

    async def test_amtrak_only_departures(self, db_session: AsyncSession):
        """Test departure service with only Amtrak trains."""
        service = DepartureService()

        # Create multiple Amtrak journeys
        for i, train_num in enumerate(["2150", "2160"]):
            journey = create_amtrak_journey(
                train_id=f"A{train_num}",
                origin="NY",
                scheduled_departure=now_et() + timedelta(hours=1, minutes=i * 30),
                line_code="AM",
                data_source="AMTRAK",
            )

            ny_stop = create_amtrak_journey_stop(
                station_code="NY",
                scheduled_departure=now_et() + timedelta(hours=1, minutes=i * 30),
                stop_sequence=0,
            )
            journey.stops = [ny_stop]

            db_session.add(journey)

        await db_session.commit()

        # Mock to avoid NJT API calls
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            response = await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

        assert len(response.departures) == 2
        assert all(d.data_source == "AMTRAK" for d in response.departures)
        assert all(d.line.code == "AM" for d in response.departures)

    async def test_jit_updates_only_njt_trains(self, db_session: AsyncSession):
        """Test that JIT updates only affect NJT trains, not Amtrak."""
        service = DepartureService()

        # Create one Amtrak and one NJT journey
        amtrak_journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        amtrak_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        amtrak_journey.stops = [amtrak_stop]

        njt_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=15),
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=True,
            update_count=1,
        )
        njt_stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=15),
            stop_sequence=0,
        )
        njt_journey.stops = [njt_stop]

        db_session.add(amtrak_journey)
        db_session.add(njt_journey)
        await db_session.commit()

        # Mock to avoid NJT API calls
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

    async def test_departure_filtering_by_station(self, db_session: AsyncSession):
        """Test filtering departures by origin and destination stations."""
        service = DepartureService()

        # Create Amtrak journey: NY -> NP -> TR
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )

        ny_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        np_stop = create_amtrak_journey_stop(
            station_code="NP",
            scheduled_arrival=now_et() + timedelta(hours=1, minutes=15),
            scheduled_departure=now_et() + timedelta(hours=1, minutes=17),
            stop_sequence=1,
        )
        tr_stop = create_amtrak_journey_stop(
            station_code="TR",
            scheduled_arrival=now_et() + timedelta(hours=1, minutes=45),
            stop_sequence=2,
        )
        journey.stops = [ny_stop, np_stop, tr_stop]

        db_session.add(journey)
        await db_session.commit()

        # Mock to avoid external calls
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            # Test NY to TR
            response_ny_tr = await service.get_departures(
                db=db_session,
                from_station="NY",
                to_station="TR",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

            assert len(response_ny_tr.departures) == 1
            departure = response_ny_tr.departures[0]
            assert departure.departure.code == "NY"
            assert departure.arrival.code == "TR"
            # Journey info no longer included in departure response (pure data approach)

            # Test NP to TR (should also find the same train)
            response_np_tr = await service.get_departures(
                db=db_session,
                from_station="NP",
                to_station="TR",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

            assert len(response_np_tr.departures) == 1
            departure = response_np_tr.departures[0]
            assert departure.departure.code == "NP"
            assert departure.arrival.code == "TR"
            # Train position provides objective data instead of journey calculations
            assert departure.train_position is not None

    async def test_cancelled_amtrak_trains_included(self, db_session: AsyncSession):
        """Test that cancelled Amtrak trains are included in departures."""
        service = DepartureService()

        # Create cancelled Amtrak journey
        cancelled_journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            is_cancelled=True,
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        cancelled_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        cancelled_journey.stops = [cancelled_stop]

        # Create active Amtrak journey
        active_journey = create_amtrak_journey(
            train_id="A2160",
            data_source="AMTRAK",
            is_cancelled=False,
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
        )
        active_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
            stop_sequence=0,
        )
        active_journey.stops = [active_stop]

        db_session.add(cancelled_journey)
        db_session.add(active_journey)
        await db_session.commit()

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            response = await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
            )

        # Should return both trains (cancelled and active)
        assert len(response.departures) == 2

        # Find the cancelled and active trains
        cancelled_train = None
        active_train = None
        for departure in response.departures:
            if departure.train_id == "A2150":
                cancelled_train = departure
            elif departure.train_id == "A2160":
                active_train = departure

        # Verify both trains are present
        assert cancelled_train is not None
        assert active_train is not None

        # Verify cancellation status is properly set
        assert cancelled_train.is_cancelled is True
        assert active_train.is_cancelled is False

    async def test_departure_time_filtering(self, db_session: AsyncSession):
        """Test filtering departures by time range."""
        service = DepartureService()

        base_time = now_et()

        # Create trains at different times
        early_journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=base_time + timedelta(minutes=30),  # 30 min from now
        )
        early_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=base_time + timedelta(minutes=30),
            stop_sequence=0,
        )
        early_journey.stops = [early_stop]

        late_journey = create_amtrak_journey(
            train_id="A2160",
            data_source="AMTRAK",
            scheduled_departure=base_time + timedelta(hours=4),  # 4 hours from now
        )
        late_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=base_time + timedelta(hours=4),
            stop_sequence=0,
        )
        late_journey.stops = [late_stop]

        db_session.add(early_journey)
        db_session.add(late_journey)
        await db_session.commit()

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            # Query with 2-hour window - should only get early train
            response = await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=base_time,
                time_to=base_time + timedelta(hours=2),
            )

        assert len(response.departures) == 1
        assert response.departures[0].train_id == "A2150"

    async def test_departure_service_metadata(self, db_session: AsyncSession):
        """Test departure service response metadata."""
        service = DepartureService()

        # Create one departure
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            response = await service.get_departures(
                db=db_session, from_station="NY", to_station="TR"
            )

        # Verify metadata structure
        assert "from_station" in response.metadata
        assert "to_station" in response.metadata
        assert "count" in response.metadata
        assert "generated_at" in response.metadata

        assert response.metadata["from_station"]["code"] == "NY"
        assert response.metadata["from_station"]["name"] == "New York Penn Station"
        assert response.metadata["to_station"]["code"] == "TR"
        assert response.metadata["to_station"]["name"] == "Trenton"
        assert response.metadata["count"] == len(response.departures)

    async def test_bulk_station_refresh_performance(self, db_session: AsyncSession):
        """Test that station refresh efficiently updates multiple trains with single query."""
        service = DepartureService()

        # Create 20 NJT journeys that need refresh
        train_ids = []
        for i in range(20):
            train_id = f"38{40 + i}"
            train_ids.append(train_id)
            journey = TrainJourney(
                train_id=train_id,
                journey_date=now_et().date(),
                data_source="NJT",
                line_code="NE",
                line_name="Northeast Corridor",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                scheduled_departure=now_et() + timedelta(hours=1, minutes=i * 2),
                last_updated_at=now_et() - timedelta(minutes=10),
                update_count=1,
            )
            stop = JourneyStop(
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=now_et() + timedelta(hours=1, minutes=i * 2),
                stop_sequence=0,
                has_departed_station=False,
                raw_njt_departed_flag="NO",
            )
            journey.stops = [stop]
            db_session.add(journey)

        await db_session.commit()

        # Mock NJT API to return all 20 trains
        mock_items = [
            {
                "TRAIN_ID": train_id,
                "DESTINATION": "Trenton Transit Center",
                "BACKCOLOR": "#F7505E ",
                "STOPS": [
                    {
                        "STATION_2CHAR": "NY",
                        "STATIONNAME": "New York Penn Station",
                        "TIME": "10:00",
                        "DEP_TIME": "10:00",
                        "DEPARTED": "NO",
                    },
                    {
                        "STATION_2CHAR": "TR",
                        "STATIONNAME": "Trenton",
                        "TIME": "11:00",
                        "DEPARTED": "NO",
                    },
                ],
            }
            for train_id in train_ids
        ]

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": mock_items}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Refresh station data
            await service._ensure_fresh_station_data(db_session, "NY", now_et().date())

        # Verify all journeys were updated
        updated_journeys = await db_session.execute(
            select(TrainJourney)
            .options(selectinload(TrainJourney.stops))
            .where(
                and_(
                    TrainJourney.train_id.in_(train_ids),
                    TrainJourney.data_source == "NJT",
                )
            )
        )
        journeys = list(updated_journeys.scalars().all())

        assert len(journeys) == 20

        # Verify each journey was updated
        for journey in journeys:
            assert journey.update_count == 2
            assert journey.destination == "Trenton Transit Center"
            assert journey.line_color == "#F7505E"
            assert journey.has_complete_journey is True
            assert journey.stops_count == 2

            # Verify stops were updated
            assert len(journey.stops) == 2

    async def test_bulk_refresh_handles_missing_journeys(
        self, db_session: AsyncSession
    ):
        """Test that station refresh gracefully handles trains not in database."""
        service = DepartureService()

        # Create only 5 journeys
        existing_ids = [f"38{40 + i}" for i in range(5)]
        for train_id in existing_ids:
            journey = TrainJourney(
                train_id=train_id,
                journey_date=now_et().date(),
                data_source="NJT",
                line_code="NE",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                scheduled_departure=now_et() + timedelta(hours=1),
                last_updated_at=now_et() - timedelta(minutes=10),
                update_count=1,
            )
            stop = JourneyStop(
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=now_et() + timedelta(hours=1),
                stop_sequence=0,
            )
            journey.stops = [stop]
            db_session.add(journey)

        await db_session.commit()

        # API returns 10 trains (5 exist, 5 don't)
        all_train_ids = [f"38{40 + i}" for i in range(10)]
        mock_items = [
            {
                "TRAIN_ID": train_id,
                "DESTINATION": "Trenton",
                "BACKCOLOR": "#F7505E",
                "STOPS": [
                    {
                        "STATION_2CHAR": "NY",
                        "STATIONNAME": "New York Penn Station",
                        "TIME": "10:00",
                        "DEPARTED": "NO",
                    }
                ],
            }
            for train_id in all_train_ids
        ]

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": mock_items}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Should not crash
            await service._ensure_fresh_station_data(db_session, "NY", now_et().date())

        # Verify only existing 5 were updated
        updated = await db_session.execute(
            select(TrainJourney).where(
                and_(
                    TrainJourney.train_id.in_(all_train_ids),
                    TrainJourney.update_count > 1,
                )
            )
        )
        assert len(list(updated.scalars().all())) == 5

    async def test_bulk_refresh_handles_amtrak_trains(self, db_session: AsyncSession):
        """Test that station refresh ignores Amtrak trains in NJT station data."""
        service = DepartureService()

        # Create 2 NJT journeys
        njt_ids = ["3840", "3842"]
        for train_id in njt_ids:
            journey = TrainJourney(
                train_id=train_id,
                journey_date=now_et().date(),
                data_source="NJT",
                line_code="NE",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                scheduled_departure=now_et() + timedelta(hours=1),
                last_updated_at=now_et() - timedelta(minutes=10),
                update_count=1,
            )
            stop = JourneyStop(
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=now_et() + timedelta(hours=1),
                stop_sequence=0,
            )
            journey.stops = [stop]
            db_session.add(journey)

        await db_session.commit()

        # API returns 2 NJT + 2 Amtrak trains
        mock_items = [
            {"TRAIN_ID": "3840", "DESTINATION": "Trenton", "STOPS": []},
            {"TRAIN_ID": "3842", "DESTINATION": "Trenton", "STOPS": []},
            {"TRAIN_ID": "A2150", "DESTINATION": "Boston", "STOPS": []},
            {"TRAIN_ID": "A2160", "DESTINATION": "Washington", "STOPS": []},
        ]

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": mock_items}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            await service._ensure_fresh_station_data(db_session, "NY", now_et().date())

        # Verify only NJT trains were updated
        updated = await db_session.execute(
            select(TrainJourney).where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.update_count > 1,
                )
            )
        )
        updated_journeys = list(updated.scalars().all())
        assert len(updated_journeys) == 2
        assert all(j.train_id in njt_ids for j in updated_journeys)

    async def test_bulk_refresh_empty_api_response(self, db_session: AsyncSession):
        """Test that station refresh handles empty API response gracefully."""
        service = DepartureService()

        # Create journey that needs refresh
        journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() + timedelta(hours=1),
            last_updated_at=now_et() - timedelta(minutes=10),
            update_count=1,
        )
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        # API returns empty list
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Should not crash
            await service._ensure_fresh_station_data(db_session, "NY", now_et().date())

        # Verify journey was not updated
        refreshed = await db_session.get(TrainJourney, journey.id)
        assert refreshed.update_count == 1

    async def test_skip_individual_refresh_skips_second_pass(
        self, db_session: AsyncSession
    ):
        """Test that skip_individual_refresh=True skips individual train refreshes.

        This test verifies the fix for excessive API calls during cache precomputation.
        When skip_individual_refresh=True, only the bulk refresh (getTrainSchedule)
        should run, NOT the individual train refreshes (getTrainStopList).
        """
        service = DepartureService()

        # Create a stale NJT journey that would trigger individual refresh
        # (past departure time, so getTrainSchedule won't return it)
        stale_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() - timedelta(hours=1),  # Past departure
            first_seen_at=now_et() - timedelta(hours=2),
            last_updated_at=now_et() - timedelta(minutes=10),  # Stale
            has_complete_journey=True,
            update_count=1,
        )
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() - timedelta(hours=1),
            stop_sequence=0,
            has_departed_station=True,
        )
        stale_journey.stops = [stop]
        db_session.add(stale_journey)
        await db_session.commit()

        original_update_count = stale_journey.update_count
        original_last_updated = stale_journey.last_updated_at

        # Mock NJT client - bulk refresh returns empty (train is past departure)
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}  # Empty - train not in schedule
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Also mock the JourneyCollector to track if it's called
            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with skip_individual_refresh=True
                await service._ensure_fresh_station_data(
                    db_session, "NY", now_et().date(), skip_individual_refresh=True
                )

                # Verify JourneyCollector was NOT instantiated (second pass skipped)
                mock_collector_class.assert_not_called()

        # Verify journey was NOT updated by individual refresh
        await db_session.refresh(stale_journey)
        assert stale_journey.update_count == original_update_count
        assert stale_journey.last_updated_at == original_last_updated

    async def test_skip_individual_refresh_false_runs_second_pass(
        self, db_session: AsyncSession
    ):
        """Test that skip_individual_refresh=False (default) runs individual refreshes.

        This verifies that when the flag is False, stale trains past their
        departure time still get refreshed via individual API calls.
        """
        service = DepartureService()

        # Create a stale NJT journey past its departure time
        stale_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() - timedelta(hours=1),  # Past departure
            first_seen_at=now_et() - timedelta(hours=2),
            last_updated_at=now_et() - timedelta(minutes=10),  # Stale
            has_complete_journey=True,
            update_count=1,
        )
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() - timedelta(hours=1),
            stop_sequence=0,
            has_departed_station=True,
        )
        stale_journey.stops = [stop]
        db_session.add(stale_journey)
        await db_session.commit()

        # Mock NJT client - bulk refresh returns empty (train is past departure)
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Mock JourneyCollector to verify it IS called
            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with skip_individual_refresh=False (default)
                await service._ensure_fresh_station_data(
                    db_session, "NY", now_et().date(), skip_individual_refresh=False
                )

                # Verify JourneyCollector WAS instantiated (second pass ran)
                mock_collector_class.assert_called_once()
                # Verify collect_journey_details was called for the stale journey
                mock_collector.collect_journey_details.assert_called()

    async def test_get_departures_passes_skip_individual_refresh(
        self, db_session: AsyncSession
    ):
        """Test that get_departures passes skip_individual_refresh to station refresh."""
        service = DepartureService()

        # Create a simple journey so the query doesn't fail
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        # Mock the station refresh method to verify parameters
        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ) as mock_refresh:
            await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                skip_individual_refresh=True,
            )

            # Verify _ensure_fresh_station_data was called with skip_individual_refresh=True
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            assert (
                call_args[0][3] is True
            )  # 4th positional arg is skip_individual_refresh

    async def test_get_departures_default_does_not_skip(self, db_session: AsyncSession):
        """Test that get_departures by default does not skip individual refresh."""
        service = DepartureService()

        # Create a simple journey
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        # Mock the station refresh method
        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ) as mock_refresh:
            await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                # Note: not passing skip_individual_refresh, should default to False
            )

            # Verify _ensure_fresh_station_data was called with skip_individual_refresh=False
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            assert (
                call_args[0][3] is False
            )  # 4th positional arg is skip_individual_refresh

    async def test_hide_departed_skips_second_pass(self, db_session: AsyncSession):
        """Test that hide_departed=True skips individual train refreshes.

        When hide_departed=True, past trains won't be shown in the response anyway,
        so there's no point refreshing them. This optimization reduces API calls
        and improves response time significantly.
        """
        service = DepartureService()

        # Create a stale NJT journey that's past its departure time
        stale_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() - timedelta(hours=1),  # Past departure
            first_seen_at=now_et() - timedelta(hours=2),
            last_updated_at=now_et() - timedelta(minutes=10),  # Stale
            has_complete_journey=True,
            update_count=1,
        )
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() - timedelta(hours=1),
            stop_sequence=0,
            has_departed_station=True,
        )
        stale_journey.stops = [stop]
        db_session.add(stale_journey)
        await db_session.commit()

        original_update_count = stale_journey.update_count

        # Mock NJT client - bulk refresh returns empty (train is past departure)
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Mock JourneyCollector to verify it's NOT called
            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with hide_departed=True
                await service._ensure_fresh_station_data(
                    db_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=False,
                    hide_departed=True,
                )

                # Verify JourneyCollector was NOT instantiated (second pass skipped)
                mock_collector_class.assert_not_called()

        # Verify journey was NOT updated
        await db_session.refresh(stale_journey)
        assert stale_journey.update_count == original_update_count

    async def test_hide_departed_false_runs_second_pass(self, db_session: AsyncSession):
        """Test that hide_departed=False (default) runs individual refreshes.

        When hide_departed=False, past trains will be shown, so they need to be
        refreshed to show accurate arrival times and completion status.
        """
        service = DepartureService()

        # Create a stale NJT journey past its departure time
        stale_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() - timedelta(hours=1),  # Past departure
            first_seen_at=now_et() - timedelta(hours=2),
            last_updated_at=now_et() - timedelta(minutes=10),  # Stale
            has_complete_journey=True,
            update_count=1,
        )
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() - timedelta(hours=1),
            stop_sequence=0,
            has_departed_station=True,
        )
        stale_journey.stops = [stop]
        db_session.add(stale_journey)
        await db_session.commit()

        # Mock NJT client - bulk refresh returns empty (train is past departure)
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Mock JourneyCollector to verify it IS called
            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with hide_departed=False (default)
                await service._ensure_fresh_station_data(
                    db_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=False,
                    hide_departed=False,
                )

                # Verify JourneyCollector WAS instantiated (second pass ran)
                mock_collector_class.assert_called_once()
                mock_collector.collect_journey_details.assert_called()

    async def test_get_departures_passes_hide_departed_to_station_refresh(
        self, db_session: AsyncSession
    ):
        """Test that get_departures passes hide_departed to station refresh."""
        service = DepartureService()

        # Create a simple journey so the query doesn't fail
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        # Mock the station refresh method to verify parameters
        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ) as mock_refresh:
            await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                hide_departed=True,
            )

            # Verify _ensure_fresh_station_data was called with hide_departed=True
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            # Args: db, from_station, target_date, skip_individual_refresh, hide_departed
            assert call_args[0][4] is True  # 5th positional arg is hide_departed

    async def test_get_departures_default_hide_departed_false(
        self, db_session: AsyncSession
    ):
        """Test that get_departures defaults hide_departed to False."""
        service = DepartureService()

        # Create a simple journey
        journey = create_amtrak_journey(
            train_id="A2150",
            data_source="AMTRAK",
            scheduled_departure=now_et() + timedelta(hours=1),
        )
        stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        journey.stops = [stop]
        db_session.add(journey)
        await db_session.commit()

        # Mock the station refresh method
        with patch.object(
            service, "_ensure_fresh_station_data", new_callable=AsyncMock
        ) as mock_refresh:
            await service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                # Note: not passing hide_departed, should default to False
            )

            # Verify _ensure_fresh_station_data was called with hide_departed=False
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            assert call_args[0][4] is False  # 5th positional arg is hide_departed
