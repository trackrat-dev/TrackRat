"""
Integration tests for departure service with Amtrak data.

Tests how the departure service integrates Amtrak and NJT data
for multi-source departures.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.services.departure import DepartureService
from trackrat.models.database import TrainJourney, JourneyStop
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

        # Mock JIT service to not make external API calls
        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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
        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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

        # Mock JIT service and verify it's only called for NJT
        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
                mock_njt_client.return_value = mock_client

                await service.get_departures(
                    db=db_session,
                    from_station="NY",
                    time_from=now_et(),
                    time_to=now_et() + timedelta(hours=3),
                )

                # Verify JIT was called with only NJT journey
                mock_jit_service.ensure_fresh_departures.assert_called_once()
                called_journeys = mock_jit_service.ensure_fresh_departures.call_args[0][
                    1
                ]
                assert len(called_journeys) == 1
                assert called_journeys[0].data_source == "NJT"

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
        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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

        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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

        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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

        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
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
