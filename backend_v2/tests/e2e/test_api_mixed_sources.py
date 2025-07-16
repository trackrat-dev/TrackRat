"""
End-to-end tests for API responses with mixed data sources.

Tests that the FastAPI endpoints properly serve both Amtrak and NJT data
with correct formatting, sorting, and filtering.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from sqlalchemy.ext.asyncio import AsyncSession
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et
from tests.factories.amtrak import create_amtrak_journey, create_amtrak_journey_stop


@pytest.mark.asyncio
class TestAPIMixedSources:
    """Test suite for API endpoints with mixed data sources."""

    async def test_departures_endpoint_mixed_sources(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test /api/trains/departures with both Amtrak and NJT trains."""

        base_time = now_et() + timedelta(hours=1)

        # Create Amtrak journey
        amtrak_journey = create_amtrak_journey(
            train_id="A2150",
            origin="NY",
            destination="Washington Union Station",
            scheduled_departure=base_time,
            data_source="AMTRAK",
            line_code="AM",
            line_name="Amtrak",
            line_color="#003366",
        )

        # Add stops to Amtrak journey
        ny_stop_amtrak = create_amtrak_journey_stop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=base_time,
            stop_sequence=0,
            track="15",
            raw_amtrak_status="Station",
        )
        tr_stop_amtrak = create_amtrak_journey_stop(
            station_code="TR",
            station_name="Trenton",
            scheduled_arrival=base_time + timedelta(minutes=45),
            stop_sequence=1,
            raw_amtrak_status="Enroute",
        )
        amtrak_journey.stops = [ny_stop_amtrak, tr_stop_amtrak]

        # Create NJT journey
        njt_journey = TrainJourney(
            train_id="3840",
            journey_date=base_time.date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            line_color="#F7505E",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=base_time + timedelta(minutes=30),
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=True,
            update_count=1,
        )

        # Add stops to NJT journey
        ny_stop_njt = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=base_time + timedelta(minutes=30),
            updated_departure=base_time + timedelta(minutes=30),
            stop_sequence=0,
            track="7",
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        )
        tr_stop_njt = JourneyStop(
            station_code="TR",
            station_name="Trenton",
            scheduled_arrival=base_time + timedelta(hours=1, minutes=15),
            updated_arrival=base_time + timedelta(hours=1, minutes=15),
            stop_sequence=1,
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        )
        njt_journey.stops = [ny_stop_njt, tr_stop_njt]

        # Add both to database
        db_session.add(amtrak_journey)
        db_session.add(njt_journey)
        await db_session.commit()

        # Query API
        response = client.get("/api/v2/trains/departures?from=NY&to=TR")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "departures" in data
        assert "metadata" in data
        assert len(data["departures"]) == 2

        # Find Amtrak and NJT trains (API sorts by departure time)
        amtrak_deps = [d for d in data["departures"] if d["data_source"] == "AMTRAK"]
        njt_deps = [d for d in data["departures"] if d["data_source"] == "NJT"]

        assert len(amtrak_deps) == 1
        assert len(njt_deps) == 1

        # Check Amtrak train
        amtrak_dep = amtrak_deps[0]
        assert amtrak_dep["train_id"] == "A2150"
        assert amtrak_dep["data_source"] == "AMTRAK"
        assert amtrak_dep["line"]["code"] == "AM"
        assert amtrak_dep["line"]["name"] == "Amtrak"
        assert amtrak_dep["line"]["color"] == "#003366"
        assert amtrak_dep["departure"]["code"] == "NY"
        assert amtrak_dep["departure"]["track"] == "15"
        assert amtrak_dep["arrival"]["code"] == "TR"

        # Check NJT train
        njt_dep = njt_deps[0]
        assert njt_dep["train_id"] == "3840"
        assert njt_dep["data_source"] == "NJT"
        assert njt_dep["line"]["code"] == "NE"
        assert njt_dep["line"]["name"] == "Northeast Corridor"
        assert njt_dep["line"]["color"] == "#F7505E"
        assert njt_dep["departure"]["code"] == "NY"
        assert njt_dep["departure"]["track"] == "7"
        assert njt_dep["arrival"]["code"] == "TR"

        # Check metadata
        metadata = data["metadata"]
        assert metadata["from_station"]["code"] == "NY"
        assert metadata["to_station"]["code"] == "TR"
        assert metadata["count"] == 2

    async def test_departures_endpoint_amtrak_only(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test departures endpoint with only Amtrak trains."""

        base_time = now_et() + timedelta(hours=1)

        # Create multiple Amtrak journeys
        for i, train_num in enumerate(["2150", "2160"]):
            journey = create_amtrak_journey(
                train_id=f"A{train_num}",
                origin="NY",
                scheduled_departure=base_time + timedelta(minutes=i * 30),
                data_source="AMTRAK",
            )

            ny_stop = create_amtrak_journey_stop(
                station_code="NY",
                scheduled_departure=base_time + timedelta(minutes=i * 30),
                stop_sequence=0,
            )
            journey.stops = [ny_stop]

            db_session.add(journey)

        await db_session.commit()

        response = client.get("/api/v2/trains/departures?from=NY")

        assert response.status_code == 200
        data = response.json()

        assert len(data["departures"]) == 2
        assert all(dep["data_source"] == "AMTRAK" for dep in data["departures"])
        assert all(dep["line"]["code"] == "AM" for dep in data["departures"])

    async def test_departures_sorting_mixed_sources(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test that departures are sorted by time across sources."""

        base_time = now_et() + timedelta(hours=1)

        # Create trains with specific timing to test sort order
        # Amtrak at 14:30
        amtrak_journey = create_amtrak_journey(
            train_id="A2150", scheduled_departure=base_time, data_source="AMTRAK"
        )
        amtrak_stop = create_amtrak_journey_stop(
            station_code="NY", scheduled_departure=base_time, stop_sequence=0
        )
        amtrak_journey.stops = [amtrak_stop]

        # NJT at 14:15 (earlier)
        njt_journey = TrainJourney(
            train_id="3840",
            journey_date=base_time.date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=base_time - timedelta(minutes=15),
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=True,
            update_count=1,
        )
        njt_stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=base_time - timedelta(minutes=15),
            stop_sequence=0,
        )
        njt_journey.stops = [njt_stop]

        db_session.add(amtrak_journey)
        db_session.add(njt_journey)
        await db_session.commit()

        response = client.get("/api/v2/trains/departures?from=NY")

        assert response.status_code == 200
        data = response.json()

        assert len(data["departures"]) == 2

        # Should be sorted by departure time (NJT first, then Amtrak)
        assert data["departures"][0]["train_id"] == "3840"  # Earlier departure
        assert data["departures"][1]["train_id"] == "A2150"  # Later departure

    async def test_api_pagination_mixed_sources(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test API pagination with mixed data sources."""

        base_time = now_et() + timedelta(hours=1)

        # Create many trains from both sources
        for i in range(5):
            # Amtrak trains
            amtrak_journey = create_amtrak_journey(
                train_id=f"A{2150+i}",
                scheduled_departure=base_time + timedelta(minutes=i * 10),
                data_source="AMTRAK",
            )
            amtrak_stop = create_amtrak_journey_stop(
                station_code="NY",
                scheduled_departure=base_time + timedelta(minutes=i * 10),
                stop_sequence=0,
            )
            amtrak_journey.stops = [amtrak_stop]
            db_session.add(amtrak_journey)

            # NJT trains
            njt_journey = TrainJourney(
                train_id=f"{3840+i}",
                journey_date=base_time.date(),
                data_source="NJT",
                line_code="NE",
                line_name="Northeast Corridor",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                scheduled_departure=base_time + timedelta(minutes=i * 10 + 5),
                first_seen_at=now_et(),
                last_updated_at=now_et(),
                has_complete_journey=True,
                update_count=1,
            )
            njt_stop = JourneyStop(
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=base_time + timedelta(minutes=i * 10 + 5),
                stop_sequence=0,
            )
            njt_journey.stops = [njt_stop]
            db_session.add(njt_journey)

        await db_session.commit()

        # Test with limit
        response = client.get("/api/v2/trains/departures?from=NY&limit=6")

        assert response.status_code == 200
        data = response.json()

        # Should return exactly 6 trains
        assert len(data["departures"]) == 6

        # Should include both sources
        data_sources = {dep["data_source"] for dep in data["departures"]}
        assert "AMTRAK" in data_sources
        assert "NJT" in data_sources

    async def test_data_freshness_mixed_sources(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test data freshness indicators in API response."""

        old_time = now_et() - timedelta(hours=2)
        recent_time = now_et() - timedelta(minutes=5)

        # Create Amtrak journey with old data
        amtrak_journey = create_amtrak_journey(
            train_id="A2150",
            scheduled_departure=now_et() + timedelta(hours=1),
            data_source="AMTRAK",
        )
        amtrak_journey.last_updated_at = old_time
        amtrak_stop = create_amtrak_journey_stop(
            station_code="NY",
            scheduled_departure=now_et() + timedelta(hours=1),
            stop_sequence=0,
        )
        amtrak_journey.stops = [amtrak_stop]

        # Create NJT journey with recent data
        njt_journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date(),
            data_source="NJT",
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
            first_seen_at=recent_time,
            last_updated_at=recent_time,
            has_complete_journey=True,
            update_count=1,
        )
        njt_stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=now_et() + timedelta(hours=1, minutes=30),
            stop_sequence=0,
        )
        njt_journey.stops = [njt_stop]

        db_session.add(amtrak_journey)
        db_session.add(njt_journey)
        await db_session.commit()

        response = client.get("/api/v2/trains/departures?from=NY")

        assert response.status_code == 200
        data = response.json()

        assert len(data["departures"]) == 2

        for departure in data["departures"]:
            assert "data_freshness" in departure
            freshness = departure["data_freshness"]
            assert "last_updated" in freshness
            assert "age_seconds" in freshness
            assert "update_count" in freshness

            if departure["train_id"] == "A2150":
                # Amtrak data should be older
                assert freshness["age_seconds"] > 7000  # > 2 hours
            else:
                # NJT data should be newer
                assert freshness["age_seconds"] < 400  # < 7 minutes

    async def test_journey_info_mixed_sources(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test journey information in API responses."""

        base_time = now_et() + timedelta(hours=1)

        # Create Amtrak journey with detailed routing
        journey = create_amtrak_journey(
            train_id="A2150",
            origin="NY",
            destination="Washington Union Station",
            scheduled_departure=base_time,
            data_source="AMTRAK",
        )

        # Add stops with travel time
        stops = [
            create_amtrak_journey_stop(
                station_code="NY", scheduled_departure=base_time, stop_sequence=0
            ),
            create_amtrak_journey_stop(
                station_code="NP",
                scheduled_arrival=base_time + timedelta(minutes=15),
                scheduled_departure=base_time + timedelta(minutes=17),
                stop_sequence=1,
            ),
            create_amtrak_journey_stop(
                station_code="TR",
                scheduled_arrival=base_time + timedelta(minutes=45),
                stop_sequence=2,
            ),
        ]
        journey.stops = stops

        db_session.add(journey)
        await db_session.commit()

        response = client.get("/api/v2/trains/departures?from=NY&to=TR")

        assert response.status_code == 200
        data = response.json()

        assert len(data["departures"]) == 1
        departure = data["departures"][0]

        # Check train position information (replaces journey)
        assert "train_position" in departure
        train_position = departure["train_position"]

        # Check basic departure info
        assert "departure" in departure
        assert "arrival" in departure
        assert departure["departure"]["code"] == "NY"
        assert departure["arrival"]["code"] == "TR"
        assert "last_departed_station_code" in train_position
        assert "next_station_code" in train_position

        # Train position provides objective data instead of journey calculations
        # Client calculates journey-specific info based on context
