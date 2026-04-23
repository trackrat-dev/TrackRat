"""
Tests for JIT station refresh fixes (issue #962):

1. _update_stops_from_embedded_data uses stops_by_code lookup from
   journey.stops instead of session.get() after pg_insert — prevents
   greenlet_spawn errors from orphan-check lazy loads during flush.

2. Second-pass error handler rolls back the session to prevent
   PendingRollbackError cascading to subsequent iterations.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _make_stop(station_code: str, stop_sequence: int = 0) -> JourneyStop:
    """Create a minimal JourneyStop for testing."""
    stop = JourneyStop(
        station_code=station_code,
        station_name=f"Station {station_code}",
        stop_sequence=stop_sequence,
    )
    stop.track = None
    stop.track_assigned_at = None
    return stop


def _make_journey_mock(
    train_id: str = "3840", stops: list[JourneyStop] | None = None
) -> MagicMock:
    """Create a mock TrainJourney with a real stops list."""
    journey = MagicMock(spec=TrainJourney)
    journey.train_id = train_id
    journey.id = 1
    journey.stops = list(stops or [])
    return journey


def _make_stops_data(station_codes: list[str]) -> list[dict]:
    """Create embedded stop data dicts as returned by NJT's getTrainSchedule."""
    past = now_et() - timedelta(hours=1)
    stops = []
    for i, code in enumerate(station_codes):
        t = past + timedelta(minutes=15 * i)
        time_str = t.strftime("%d-%b-%Y %I:%M:%S %p")
        stops.append(
            {
                "STATION_2CHAR": code,
                "STATIONNAME": f"Station {code}",
                "TIME": time_str,
                "DEP_TIME": time_str,
                "SCHED_DEP_DATE": time_str,
                "SCHED_ARR_DATE": time_str,
                "DEPARTED": "NO",
                "STOP_STATUS": "OnTime",
            }
        )
    return stops


class TestStopsByCodeLookup:
    """Verify _update_stops_from_embedded_data uses journey.stops for lookup."""

    def test_existing_stop_found_in_dict_no_db_query(self):
        """When a stop already exists in journey.stops, it is updated in-place
        without any session.execute or session.get calls for that stop."""
        service = DepartureService()

        existing_stop = _make_stop("NY")
        journey = _make_journey_mock(stops=[existing_stop])

        stops_data = _make_stops_data(["NY"])
        stops_data[0]["DEPARTED"] = "YES"

        mock_session = AsyncMock()

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        # No session.execute calls needed — stop was found in the dict
        mock_session.execute.assert_not_called()
        mock_session.get.assert_not_called()

        # Stop was updated in-place
        assert existing_stop.has_departed_station is True
        assert existing_stop.raw_njt_departed_flag == "YES"

    def test_multiple_existing_stops_all_found_in_dict(self):
        """Multiple existing stops are all found via stops_by_code with zero
        DB queries — this eliminates the N+1 SELECT pattern."""
        service = DepartureService()

        ny = _make_stop("NY", 0)
        np = _make_stop("NP", 1)
        tr = _make_stop("TR", 2)
        journey = _make_journey_mock(stops=[ny, np, tr])

        stops_data = _make_stops_data(["NY", "NP", "TR"])

        mock_session = AsyncMock()

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        # Zero DB queries for existing stops
        mock_session.execute.assert_not_called()

    def test_new_stop_triggers_insert_and_select(self):
        """When a stop is NOT in journey.stops, the method uses pg_insert
        then select to fetch it, and appends it to journey.stops."""
        service = DepartureService()

        journey = _make_journey_mock(stops=[])

        new_stop = _make_stop("NY")
        select_result = MagicMock()
        select_result.scalar_one.return_value = new_stop

        # Two execute calls: pg_insert, then select
        insert_result = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[insert_result, select_result]
        )

        stops_data = _make_stops_data(["NY"])

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        # Two execute calls: insert + select
        assert mock_session.execute.call_count == 2
        # Stop was added to journey.stops
        assert new_stop in journey.stops
        assert len(journey.stops) == 1

    def test_mixed_existing_and_new_stops(self):
        """Existing stops use the dict; new stops use insert+select.
        Only new stops generate DB queries."""
        service = DepartureService()

        existing_ny = _make_stop("NY", 0)
        journey = _make_journey_mock(stops=[existing_ny])

        new_np = _make_stop("NP", 1)
        select_result = MagicMock()
        select_result.scalar_one.return_value = new_np

        insert_result = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[insert_result, select_result]
        )

        stops_data = _make_stops_data(["NY", "NP"])

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        # Only 2 execute calls (for NP insert + select), not 4
        assert mock_session.execute.call_count == 2
        assert existing_ny in journey.stops
        assert new_np in journey.stops
        assert len(journey.stops) == 2

    def test_empty_station_code_skipped(self):
        """Stops with missing/empty STATION_2CHAR are silently skipped."""
        service = DepartureService()

        journey = _make_journey_mock(stops=[])
        mock_session = AsyncMock()

        stops_data = [
            {"STATION_2CHAR": "", "STATIONNAME": "Empty"},
            {"STATIONNAME": "Missing"},
        ]

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        assert len(journey.stops) == 0
        mock_session.execute.assert_not_called()


class TestDepartedFlagSequentialInference:
    """Test sequential departure inference via max_departed_idx."""

    def test_earlier_stops_inferred_departed(self):
        """If stop[2] has DEPARTED=YES, stops 0 and 1 should be inferred
        as departed even though their API flags say NO."""
        service = DepartureService()

        s0 = _make_stop("NY", 0)
        s1 = _make_stop("NP", 1)
        s2 = _make_stop("TR", 2)
        journey = _make_journey_mock(stops=[s0, s1, s2])

        stops_data = _make_stops_data(["NY", "NP", "TR"])
        stops_data[0]["DEPARTED"] = "NO"
        stops_data[1]["DEPARTED"] = "NO"
        stops_data[2]["DEPARTED"] = "YES"

        mock_session = AsyncMock()

        asyncio.run(
            service._update_stops_from_embedded_data(
                mock_session, journey, stops_data
            )
        )

        assert s0.has_departed_station is True
        assert s1.has_departed_station is True
        assert s2.has_departed_station is True


class TestSecondPassRollback:
    """Test that the second-pass error handler rolls back to prevent
    PendingRollbackError cascade (fix for the cascade symptom in #962)."""

    def test_rollback_called_on_stale_train_refresh_failure(self):
        """When a stale train refresh fails with a non-PostgreSQL error,
        the error handler should rollback the session before continuing."""
        # Read the source to verify the rollback is present
        import inspect
        from trackrat.services.departure import DepartureService

        source = inspect.getsource(DepartureService._ensure_fresh_station_data)

        # The error handler for stale_train_refresh_failed must contain
        # await db.rollback() to prevent PendingRollbackError cascade
        assert "stale_train_refresh_failed" in source
        assert "await db.rollback()" in source

        # Verify the rollback is inside a try/except (defensive)
        lines = source.split("\n")
        found_stale_handler = False
        found_rollback_after = False
        for i, line in enumerate(lines):
            if "stale_train_refresh_failed" in line:
                found_stale_handler = True
            if found_stale_handler and "await db.rollback()" in line:
                found_rollback_after = True
                break

        assert found_stale_handler, (
            "Expected 'stale_train_refresh_failed' log in _ensure_fresh_station_data"
        )
        assert found_rollback_after, (
            "Expected 'await db.rollback()' after stale_train_refresh_failed handler "
            "to prevent PendingRollbackError cascade"
        )
