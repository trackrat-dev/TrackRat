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
from datetime import datetime, timedelta
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


NJT_BOARD_TIME_FORMAT = "%d-%b-%Y %I:%M:%S %p"


def _make_stops_data(
    station_codes: list[str], delay_minutes: int = 0
) -> list[dict[str, str]]:
    """Create embedded stop data dicts as returned by NJT's getTrainSchedule.

    ``delay_minutes`` moves the *live* fields away from the immutable SCHED_*
    ones, which is the only way to tell a real reading from the timetable in a
    payload where an on-time train has them all equal. It has to be applied
    according to NJT's position-dependent semantics: at the origin (index 0)
    DEP_TIME carries the live departure and TIME the schedule, while at every
    later stop that is inverted — TIME is the live estimate and DEP_TIME stays
    the schedule.
    """
    past = now_et() - timedelta(hours=1)
    stops = []
    for i, code in enumerate(station_codes):
        t = past + timedelta(minutes=15 * i)
        scheduled = t.strftime(NJT_BOARD_TIME_FORMAT)
        live = (t + timedelta(minutes=delay_minutes)).strftime(NJT_BOARD_TIME_FORMAT)
        is_origin = i == 0
        stops.append(
            {
                "STATION_2CHAR": code,
                "STATIONNAME": f"Station {code}",
                "TIME": scheduled if is_origin else live,
                "DEP_TIME": live if is_origin else scheduled,
                "SCHED_DEP_DATE": scheduled,
                "SCHED_ARR_DATE": scheduled,
                "DEPARTED": "NO",
                "STOP_STATUS": "OnTime",
            }
        )
    return stops


class TestStationBoardCancellationDetection:
    """The station-board refresh must apply NJT's cancellation rule (#1670).

    This is the highest-frequency NJT refresh path — it runs on every departure
    board JIT refresh, far more often than getTrainStopList collection — and it
    stamps last_updated_at, marking the journey fresh for the periodic sweep and
    the JIT staleness check. Reading the board's STOP_STATUS values without
    acting on them therefore actively *delays* cancellation detection rather
    than merely failing to help.

    Train 3918 (2026-07-28) is the reference case: it left Trenton, was annulled
    en route, and TrackRat reported it running for 65 minutes.
    """

    def test_terminal_cancelled_marks_journey_cancelled(self):
        """3918's shape: origin departed and on time, every later stop CANCELLED."""
        service = DepartureService()

        stops = [_make_stop(code, i) for i, code in enumerate(["TR", "PJ", "NY"])]
        journey = _make_journey_mock(train_id="3918", stops=stops)
        journey.is_cancelled = False
        journey.cancellation_reason = None

        stops_data = _make_stops_data(["TR", "PJ", "NY"])
        stops_data[0]["STOP_STATUS"] = "ON TIME"
        stops_data[0]["DEPARTED"] = "YES"
        stops_data[1]["STOP_STATUS"] = "CANCELLED"
        stops_data[2]["STOP_STATUS"] = "CANCELLED"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == (
            "Journey terminated before reaching destination"
        )

    def test_all_stops_cancelled_marks_journey_cancelled(self):
        """A train annulled before it ever ran."""
        service = DepartureService()

        stops = [_make_stop(code, i) for i, code in enumerate(["TR", "PJ", "NY"])]
        journey = _make_journey_mock(stops=stops)
        journey.is_cancelled = False
        journey.cancellation_reason = None

        stops_data = _make_stops_data(["TR", "PJ", "NY"])
        for stop_data in stops_data:
            stop_data["STOP_STATUS"] = "CANCELLED"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == "All stops cancelled by NJT"

    def test_running_train_is_not_marked_cancelled(self):
        """No false positives on a normal board payload."""
        service = DepartureService()

        stops = [_make_stop(code, i) for i, code in enumerate(["TR", "PJ", "NY"])]
        journey = _make_journey_mock(stops=stops)
        journey.is_cancelled = False
        journey.cancellation_reason = None

        stops_data = _make_stops_data(["TR", "PJ", "NY"])
        stops_data[1]["STOP_STATUS"] = "LATE"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert journey.is_cancelled is False
        assert journey.cancellation_reason is None

    def test_intermediate_only_cancellation_does_not_cancel_journey(self):
        """A skipped intermediate stop is not a cancelled train — the terminal
        still being served means the train completes its journey."""
        service = DepartureService()

        stops = [_make_stop(code, i) for i, code in enumerate(["TR", "PJ", "NY"])]
        journey = _make_journey_mock(stops=stops)
        journey.is_cancelled = False
        journey.cancellation_reason = None

        stops_data = _make_stops_data(["TR", "PJ", "NY"])
        stops_data[1]["STOP_STATUS"] = "CANCELLED"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert journey.is_cancelled is False

    def test_existing_cancellation_reason_is_not_overwritten(self):
        """Clearing/re-deriving a cancellation is discovery's job (#1498); this
        path only ever sets the flag, and never restates a reason already
        recorded by the fuller getTrainStopList collection."""
        service = DepartureService()

        stops = [_make_stop(code, i) for i, code in enumerate(["TR", "NY"])]
        journey = _make_journey_mock(stops=stops)
        journey.is_cancelled = True
        journey.cancellation_reason = "All stops cancelled by NJT"

        stops_data = _make_stops_data(["TR", "NY"])
        stops_data[0]["STOP_STATUS"] = "ON TIME"
        stops_data[1]["STOP_STATUS"] = "CANCELLED"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == "All stops cancelled by NJT"


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
            if "retry_on_deadlock(db, refresh_journey)" in line and i + 5 < len(lines):
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


class TestStationBoardActualDeparture:
    """The board refresh must record a live reading, never the timetable (#1768).

    This is the highest-frequency NJT write path, and it assigned

        stop.actual_departure = stop.scheduled_arrival or stop.scheduled_departure

    under a comment reading "Use arrival time (live estimate from TIME field) or
    scheduled departure". The comment named the right value; the code read the
    wrong column. ``scheduled_arrival`` is the timetable's arrival — a different
    column from the live ``updated_arrival`` the same loop parses out of TIME
    thirty lines earlier — and it is almost always NULL for NJT, so every
    departed stop fell through to its own ``scheduled_departure``.

    The result is indistinguishable from a train that ran on time. On train 7825
    (NY→TR, 35 minutes late) six of eleven departed stops recorded their
    schedule as their actual departure, and the train-detail rows for those
    stops dropped their delay badge while their neighbours showed "+35m delay".
    Because both writers only ever filled a NULL, the wrong value was then
    frozen for the life of the row.
    """

    @staticmethod
    def _service_and_journey(
        station_codes: list[str], train_id: str = "7825"
    ) -> tuple[DepartureService, MagicMock, list[JourneyStop]]:
        stops = [_make_stop(code, i) for i, code in enumerate(station_codes)]
        journey = _make_journey_mock(train_id=train_id, stops=stops)
        journey.is_cancelled = False
        journey.cancellation_reason = None
        # NJT's origin/intermediate inversion is resolved against this.
        journey.origin_station_code = station_codes[0]
        return DepartureService(), journey, stops

    def test_departed_stop_records_live_estimate_not_schedule(self):
        """The #1768 shape: a stop passed 35 minutes late."""
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"], delay_minutes=35)
        stops_data[1]["DEPARTED"] = "YES"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        na = stops[1]
        print(f"  - scheduled_departure: {na.scheduled_departure}")
        print(f"  - updated_arrival (live TIME): {na.updated_arrival}")
        print(f"  - actual_departure: {na.actual_departure}")

        assert na.has_departed_station is True
        assert na.actual_departure == na.updated_arrival, (
            "the board's live TIME reading is what actually happened at this "
            f"stop, but actual_departure is {na.actual_departure}"
        )
        assert na.actual_departure != na.scheduled_departure, (
            "recording the timetable is what made a 35-minute-late train render "
            "as on time in #1768"
        )
        delay = (na.actual_departure - na.scheduled_departure).total_seconds() / 60
        assert delay == pytest.approx(
            35, abs=0.1
        ), f"the stop must now compute a 35-minute delay, got {delay:.1f}"

    def test_sequential_inference_records_live_estimate_not_schedule(self):
        """The second call site carried an identical copy of the same bug."""
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"], delay_minutes=35)
        # NA is not flagged, but the later TR is — so NA must have departed.
        stops_data[2]["DEPARTED"] = "YES"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        na = stops[1]
        assert na.has_departed_station is True
        assert na.actual_departure == na.updated_arrival, (
            f"sequential inference must record the live reading, got "
            f"{na.actual_departure} against a schedule of {na.scheduled_departure}"
        )

    def test_records_nothing_when_live_estimate_is_future(self):
        """NJT flips DEPARTED=YES before its estimate has come to pass.

        Withholding the timestamp is the whole point: every consumer has an
        honest fallback for NULL, and none can tell a schedule stamped into the
        actuals column apart from a punctual train.
        """
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"])
        stops_data[1]["DEPARTED"] = "YES"
        stops_data[1]["TIME"] = (now_et() + timedelta(minutes=5)).strftime(
            NJT_BOARD_TIME_FORMAT
        )

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        na = stops[1]
        print(f"  - scheduled_departure: {na.scheduled_departure}")
        print(f"  - actual_departure: {na.actual_departure}")

        assert (
            na.has_departed_station is True
        ), "the fix withholds the timestamp, not the departure itself"
        assert na.actual_departure is None, (
            f"got {na.actual_departure}; scheduled_departure is "
            f"{na.scheduled_departure} and scheduled_arrival is "
            f"{na.scheduled_arrival} — neither may be recorded as an actual"
        )

    def test_origin_records_its_live_dep_time(self):
        """At the origin the live value is DEP_TIME, not TIME.

        Guards the fix against flattening NJT's position-dependent semantics:
        reading TIME here would record the immutable schedule and report a
        late-leaving train as punctual out of its origin.
        """
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"], delay_minutes=35)
        stops_data[0]["DEPARTED"] = "YES"

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        ny = stops[0]
        print(f"  - scheduled_departure (TIME): {ny.scheduled_departure}")
        print(f"  - updated_departure (live DEP_TIME): {ny.updated_departure}")
        print(f"  - actual_departure: {ny.actual_departure}")

        assert ny.actual_departure == ny.updated_departure, (
            f"the origin's live DEP_TIME must be recorded, got "
            f"{ny.actual_departure}"
        )
        assert ny.actual_departure != ny.scheduled_departure

    def test_repairs_departure_recorded_before_arrival(self):
        """Rows the old code already wrote are corrupt and were frozen that way.

        Train 7825's Newark Airport stop was serving actual_departure 08:38:30
        against actual_arrival 09:15:30 — the train left 37 minutes before it
        got there. Since both writers only filled a NULL, nothing would ever
        have corrected it.
        """
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"], delay_minutes=35)
        stops_data[1]["DEPARTED"] = "YES"

        na = stops[1]
        scheduled = datetime.strptime(
            stops_data[1]["SCHED_DEP_DATE"], NJT_BOARD_TIME_FORMAT
        ).replace(tzinfo=now_et().tzinfo)
        live = datetime.strptime(stops_data[1]["TIME"], NJT_BOARD_TIME_FORMAT).replace(
            tzinfo=now_et().tzinfo
        )
        na.scheduled_departure = scheduled
        na.actual_departure = scheduled  # what the old code wrote
        na.actual_arrival = live  # 35 minutes after its own "departure"
        na.has_departed_station = True

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        print(f"  - seeded actual_departure: {scheduled} (the schedule)")
        print(f"  - recorded actual_arrival: {na.actual_arrival}")
        print(f"  - repaired actual_departure: {na.actual_departure}")

        assert na.actual_departure == na.updated_arrival, (
            "the impossible ordering must be replaced by the live reading, got "
            f"{na.actual_departure}"
        )
        assert na.actual_departure >= na.actual_arrival, (
            "after repair the stop must no longer claim the train left before "
            "it arrived"
        )

    def test_does_not_overwrite_a_valid_recorded_departure(self):
        """The freeze still holds for values that can be true.

        NJT revises its estimates for hours after a train passes; the reading
        taken while the train was at the stop is the accurate one. Only the
        impossible ordering may reopen it.
        """
        service, journey, stops = self._service_and_journey(["NY", "NA", "TR"])

        stops_data = _make_stops_data(["NY", "NA", "TR"], delay_minutes=35)
        stops_data[1]["DEPARTED"] = "YES"

        na = stops[1]
        captured = now_et() - timedelta(minutes=20)
        na.actual_departure = captured
        na.actual_arrival = captured
        na.has_departed_station = True

        asyncio.run(
            service._update_stops_from_embedded_data(AsyncMock(), journey, stops_data)
        )

        assert (
            na.actual_departure == captured
        ), f"a valid first capture must not be revised, got {na.actual_departure}"
