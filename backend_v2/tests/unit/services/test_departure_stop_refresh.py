"""
Tests for JIT station refresh fixes:

1. (#962) _update_stops_from_embedded_data uses stops_by_code lookup from
   journey.stops instead of session.get() after pg_insert — prevents
   greenlet_spawn errors from orphan-check lazy loads during flush.

2. (#1196) Second-pass per-journey refresh uses per-journey commit
   instead of `begin_nested()` around `retry_on_deadlock`. The latter
   combination corrupted SAVEPOINT state on deadlock retry (inner
   rollback discards the outer transaction) and triggered greenlet
   errors on subsequent flushes.
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
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
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
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
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
        mock_session.execute = AsyncMock(side_effect=[insert_result, select_result])

        stops_data = _make_stops_data(["NY"])

        asyncio.run(
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
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
        mock_session.execute = AsyncMock(side_effect=[insert_result, select_result])

        stops_data = _make_stops_data(["NY", "NP"])

        asyncio.run(
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
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
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
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
            service._update_stops_from_embedded_data(mock_session, journey, stops_data)
        )

        assert s0.has_departed_station is True
        assert s1.has_departed_station is True
        assert s2.has_departed_station is True


class TestSecondPassPerJourneyCommit:
    """Verify second-pass per-journey refresh uses per-journey commit instead
    of `begin_nested()` for isolation (fix for #1196).

    Background: issue #962 wrapped each stale-journey refresh in
    `async with db.begin_nested(): await retry_on_deadlock(db, refresh_journey)`
    to isolate failures. That combination is broken — `retry_on_deadlock`
    calls `await session.rollback()` on retry, which rolls back the *outer*
    transaction (not the savepoint), leaving the SAVEPOINT state inconsistent
    and triggering `greenlet_spawn has not been called; can't call
    await_only() here` on subsequent flushes. Recurred 3x in 48h of
    production logs.

    The fix is per-journey commit: each successful refresh commits
    immediately, preserving prior work; each failure rolls back only the
    current journey's partial state, leaving the session clean for the
    next iteration.
    """

    def test_no_begin_nested_around_retry_on_deadlock(self):
        """`begin_nested()` must not wrap `retry_on_deadlock` — the two
        primitives are incompatible (see class docstring)."""
        import inspect
        from trackrat.services.departure import DepartureService

        source = inspect.getsource(DepartureService._ensure_fresh_station_data)

        assert (
            "stale_train_refresh_failed" in source
        ), "Expected 'stale_train_refresh_failed' log in _ensure_fresh_station_data"

        # Strip comments so the comment that documents the fix doesn't
        # trip the substring check. Keep only code.
        code_lines = []
        for line in source.split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            code_lines.append(line)

        # Walk the code and verify no `begin_nested():` (as a statement,
        # not a string in a comment) is followed within a few lines by a
        # call to `retry_on_deadlock(`.
        for i, line in enumerate(code_lines):
            if "begin_nested():" in line:
                window = "\n".join(code_lines[i : i + 5])
                assert "retry_on_deadlock(" not in window, (
                    f"Found `begin_nested()` wrapping `retry_on_deadlock` "
                    f"at code line {i}. This combination is broken — the "
                    f"inner rollback discards the savepoint, triggering "
                    f"greenlet errors on subsequent flushes.\n\nContext:\n"
                    f"{window}"
                )

    def test_per_journey_commit_isolates_failures(self):
        """Each successful per-journey refresh must commit before the next
        iteration so a later failure cannot erase prior successes."""
        import inspect
        from trackrat.services.departure import DepartureService

        source = inspect.getsource(DepartureService._ensure_fresh_station_data)

        # Find the per-journey loop: retry_on_deadlock(db, refresh_journey)
        # must be followed by `await db.commit()` and the success log
        # before the next iteration.
        lines = source.split("\n")
        commit_after_retry = False
        for i, line in enumerate(lines):
            if (
                "retry_on_deadlock(db, refresh_journey)" in line
                and i + 5 < len(lines)
            ):
                window = "\n".join(lines[i : i + 5])
                if "await db.commit()" in window:
                    commit_after_retry = True
                    break
        assert commit_after_retry, (
            "Expected `await db.commit()` immediately after "
            "`retry_on_deadlock(db, refresh_journey)` so each successful "
            "stale-train refresh is durable before the next iteration."
        )

    def test_per_journey_rollback_clears_session_on_failure(self):
        """Both failure branches in the per-journey loop must `db.rollback()`
        so the next iteration starts with a clean session — otherwise
        PendingRollbackError cascades through the rest of the batch."""
        import inspect
        from trackrat.services.departure import DepartureService

        source = inspect.getsource(DepartureService._ensure_fresh_station_data)

        # Both handlers must rollback before logging.
        assert source.count("await db.rollback()") >= 2, (
            "Expected at least two `await db.rollback()` calls in "
            "_ensure_fresh_station_data — one in each per-journey except "
            "handler (TrainNotFoundError and generic Exception)."
        )

        # Verify the TrainNotFoundError handler rolls back.
        not_found_idx = source.find("except TrainNotFoundError")
        warn_idx = source.find('"stale_train_not_found"')
        assert not_found_idx != -1 and warn_idx > not_found_idx
        not_found_block = source[not_found_idx:warn_idx]
        assert "await db.rollback()" in not_found_block, (
            "TrainNotFoundError handler must roll back the session to "
            "clear any pending state before the next iteration."
        )

        # Verify the generic Exception handler rolls back.
        generic_idx = source.find('"stale_train_refresh_failed"')
        assert generic_idx != -1
        # Look backwards from the warning log to the `except Exception`.
        prelude = source[:generic_idx]
        last_except = prelude.rfind("except Exception")
        assert last_except != -1
        generic_block = source[last_except:generic_idx]
        assert "await db.rollback()" in generic_block, (
            "Generic Exception handler must roll back the session to clear "
            "any pending state before the next iteration."
        )
