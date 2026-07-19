"""Unit tests for SeptaRailCollector.

The heart of these tests is :func:`resolve_arrivals`, which reconstructs
absolute stop times by applying the feed's per-stop *delays* to the GTFS static
schedule using GTFS-RT propagation semantics (a delay applies to its stop and
every later stop until the next update; stops before the first update are
already-passed and excluded). ``_generate_train_id`` extracts the train number
from SEPTA's ``<short_name>_<YYYYMMDD>_<SID...>`` trip_ids, while
``_resolve_static_schedule`` joins a delay-only trip to the GTFS static schedule
using the *operating* day (wall clock), not the stale version date in the trip_id.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.septa_rr.client import (
    SeptaRailArrival,
    SeptaRailClient,
    SeptaRailStopUpdate,
    SeptaRailTripUpdate,
)
from trackrat.collectors.septa_rr.collector import (
    SeptaRailCollector,
    _generate_train_id,
    resolve_arrivals,
)
from trackrat.utils.time import ET


def _static_stop(
    station_code: str,
    stop_sequence: int | None,
    arrival: datetime,
    departure: datetime | None = None,
) -> dict:
    """Build one GTFS static stop dict (tz-aware ET times), as the collector expects."""
    return {
        "station_code": station_code,
        "stop_sequence": stop_sequence,
        "arrival_time": arrival,
        "departure_time": departure if departure is not None else arrival,
    }


def _trip(stop_updates: list[SeptaRailStopUpdate], **overrides) -> SeptaRailTripUpdate:
    defaults = {
        "trip_id": "CHW8312_20260718_SID189411",
        "route_id": "CHW",
        "direction_id": 0,
        "vehicle_label": "805",
    }
    defaults.update(overrides)
    return SeptaRailTripUpdate(stop_updates=stop_updates, **defaults)


# A fixed base time so delay arithmetic is easy to reason about.
_BASE = ET.localize(datetime(2026, 7, 18, 10, 0, 0))


class TestGenerateTrainId:
    """First underscore-segment is the GTFS trip_short_name."""

    def test_standard_trip_id(self):
        assert _generate_train_id("CHW8312_20260718_SID189411") == "CHW8312"

    def test_no_underscore_returns_input(self):
        assert _generate_train_id("CHW8312") == "CHW8312"

    def test_leading_underscore_falls_back_to_full_id(self):
        # split("_", 1)[0] is "" here, so the `or trip_id` fallback kicks in.
        assert _generate_train_id("_20260718_SID1") == "_20260718_SID1"

    def test_empty_string(self):
        assert _generate_train_id("") == ""


class TestResolveStaticSchedule:
    """The operating day comes from the wall clock, NOT the trip_id's version date.

    SEPTA RR trip_ids embed a stale schedule-version date bound to the service_id
    (e.g. ``_20260621_`` served weeks later); using it to look up active GTFS
    services returns nothing, which silently dropped ~90% of live trains.

    Which wall-clock day is tried *first* matters just as much. SEPTA's weekday
    service_ids (SID189324 et al., Mon-Fri) are active on both sides of a weeknight
    midnight, so a post-midnight train matches today's schedule too. Because
    ``get_static_stop_times`` anchors every stop time to the date it is handed,
    resolving to the wrong day shifts the whole reconstructed journey ~24h forward
    and files it under a duplicate ``journey_date``. The ordering tests below
    therefore make BOTH days match — the real production shape — so a regression to
    unconditional today-first fails them instead of passing on a rigged stub.
    """

    @pytest.fixture
    def collector(self):
        return SeptaRailCollector(client=AsyncMock(spec=SeptaRailClient))

    @staticmethod
    def _stub_days(collector, matching_dates, stops):
        """Stub the GTFS lookup to match ``matching_dates``; record query order."""
        seen_dates: list[date] = []

        async def fake_get(_session, _source, _trip_id, target_date):
            seen_dates.append(target_date)
            return stops if target_date in matching_dates else []

        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(side_effect=fake_get)
        return seen_dates

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_uses_today_not_trip_id_version_date(self, mock_now, collector):
        """A trip_id embedding a month-old version date still resolves via today."""
        mock_now.return_value = ET.localize(datetime(2026, 7, 19, 15, 0, 0))
        stops = [_static_stop("SEPR90801", 1, _BASE)]
        seen_dates: list[date] = []

        async def fake_get(_session, _source, _trip_id, target_date):
            seen_dates.append(target_date)
            return stops if target_date == date(2026, 7, 19) else []

        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(side_effect=fake_get)

        # Version date in the trip_id is 2026-06-21 — must never be queried.
        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)],
            trip_id="AIR2453_20260621_SID189896",
        )
        resolved_date, resolved_stops = await collector._resolve_static_schedule(
            AsyncMock(), trip
        )

        assert resolved_date == date(2026, 7, 19)
        assert resolved_stops == stops
        assert date(2026, 6, 21) not in seen_dates, "must not use the version date"
        assert seen_dates == [date(2026, 7, 19)], "today matches → no extra lookup"

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_prefers_yesterday_before_rollover_when_both_days_match(
        self, mock_now, collector
    ):
        """Post-midnight, yesterday must win even though today also matches.

        The production case: 00:15 on a Tuesday, a Monday-night train still in the
        feed on a Mon-Fri service_id that is active Tuesday too. Today-first would
        match Tuesday and shift the whole journey ~24h forward, so yesterday must be
        queried first and today must never be reached.
        """
        mock_now.return_value = ET.localize(datetime(2026, 7, 21, 0, 15, 0))  # Tuesday
        stops = [_static_stop("SEPR90801", 1, _BASE)]
        both = {date(2026, 7, 20), date(2026, 7, 21)}
        seen_dates = self._stub_days(collector, both, stops)

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)]
        )
        resolved_date, resolved_stops = await collector._resolve_static_schedule(
            AsyncMock(), trip
        )

        assert resolved_date == date(2026, 7, 20), (
            "a 00:15 train belongs to the previous service day, but resolved to "
            f"{resolved_date}"
        )
        assert resolved_stops == stops
        assert seen_dates == [date(2026, 7, 20)], (
            "yesterday must be queried first and win outright before the rollover; "
            f"query order was {seen_dates}"
        )

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_prefers_today_after_rollover_when_both_days_match(
        self, mock_now, collector
    ):
        """Mid-afternoon, today must win even though yesterday also matches."""
        mock_now.return_value = ET.localize(datetime(2026, 7, 21, 15, 0, 0))
        stops = [_static_stop("SEPR90801", 1, _BASE)]
        both = {date(2026, 7, 20), date(2026, 7, 21)}
        seen_dates = self._stub_days(collector, both, stops)

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)]
        )
        resolved_date, resolved_stops = await collector._resolve_static_schedule(
            AsyncMock(), trip
        )

        assert resolved_date == date(2026, 7, 21)
        assert resolved_stops == stops
        assert seen_dates == [date(2026, 7, 21)], (
            f"today must win outright after the rollover; query order was {seen_dates}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "hour,expected_first",
        [
            (0, date(2026, 7, 20)),  # 00:00 — yesterday's service day still running
            (1, date(2026, 7, 20)),  # 01:33 is the latest scheduled arrival
            (2, date(2026, 7, 20)),  # dead zone, no train running either way
            (3, date(2026, 7, 21)),  # rollover: first departure of the day is 03:49
            (4, date(2026, 7, 21)),
            (23, date(2026, 7, 21)),
        ],
    )
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_rollover_boundary_is_inside_the_service_gap(
        self, mock_now, collector, hour, expected_first
    ):
        """The 03:00 rollover sits in the 01:33-03:49 gap when nothing is running.

        Pins the constant against both failure modes: rolling over too early would
        mis-assign trains still finishing yesterday's service day, too late would
        mis-assign the 03:49 first departures of today.
        """
        mock_now.return_value = ET.localize(datetime(2026, 7, 21, hour, 0, 0))
        stops = [_static_stop("SEPR90801", 1, _BASE)]
        both = {date(2026, 7, 20), date(2026, 7, 21)}
        seen_dates = self._stub_days(collector, both, stops)

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)]
        )
        resolved_date, _ = await collector._resolve_static_schedule(AsyncMock(), trip)

        assert resolved_date == expected_first, (
            f"at {hour:02d}:00 ET the operating day must resolve to {expected_first}, "
            f"got {resolved_date}"
        )
        assert seen_dates == [expected_first]

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_falls_through_to_today_before_rollover_when_yesterday_missing(
        self, mock_now, collector
    ):
        """Before the rollover, a yesterday miss still falls through to today.

        Covers the service_id boundary (e.g. Sunday 00:15, where the Saturday-only
        service that ran the train is no longer active) — best effort beats dropping
        the trip entirely.
        """
        mock_now.return_value = ET.localize(datetime(2026, 7, 19, 0, 15, 0))
        stops = [_static_stop("SEPR90801", 1, _BASE)]
        seen_dates = self._stub_days(collector, {date(2026, 7, 19)}, stops)

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)]
        )
        resolved_date, resolved_stops = await collector._resolve_static_schedule(
            AsyncMock(), trip
        )

        assert resolved_date == date(2026, 7, 19)
        assert resolved_stops == stops
        assert seen_dates == [date(2026, 7, 18), date(2026, 7, 19)], (
            f"yesterday must be tried before today, got {seen_dates}"
        )

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_returns_none_when_neither_day_matches(self, mock_now, collector):
        """No static match on today or yesterday → (None, None)."""
        mock_now.return_value = ET.localize(datetime(2026, 7, 19, 15, 0, 0))
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=[])

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=0, departure_delay=0)]
        )
        resolved_date, resolved_stops = await collector._resolve_static_schedule(
            AsyncMock(), trip
        )

        assert resolved_date is None
        assert resolved_stops is None
        # Both today and yesterday were attempted before giving up.
        assert collector._gtfs_service.get_static_stop_times.await_count == 2


class TestResolveArrivals:
    """Delay-to-absolute-time reconstruction — the collector's core logic."""

    def test_single_update_excludes_passed_stops_and_applies_delay(self):
        """One update at seq 3, delay 120s: seq 1-2 are excluded (already passed),
        seq 3-5 all shift by +120s."""
        stops = [
            _static_stop("SEPR90801", 1, _BASE + timedelta(minutes=0)),
            _static_stop("SEPR90802", 2, _BASE + timedelta(minutes=5)),
            _static_stop("SEPR90803", 3, _BASE + timedelta(minutes=10)),
            _static_stop("SEPR90804", 4, _BASE + timedelta(minutes=15)),
            _static_stop("SEPR90805", 5, _BASE + timedelta(minutes=20)),
        ]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=3, arrival_delay=120, departure_delay=120
                )
            ]
        )

        arrivals = resolve_arrivals(trip, stops)

        codes = [a.station_code for a in arrivals]
        assert codes == ["SEPR90803", "SEPR90804", "SEPR90805"]
        assert all(a.delay_seconds == 120 for a in arrivals)
        # Exact arithmetic: static + 120s.
        assert arrivals[0].arrival_time == _BASE + timedelta(minutes=10, seconds=120)
        assert arrivals[1].arrival_time == _BASE + timedelta(minutes=15, seconds=120)
        assert arrivals[2].arrival_time == _BASE + timedelta(minutes=20, seconds=120)

    def test_two_updates_propagate_between_and_after(self):
        """Updates at seq 2 (D=60) and seq 4 (D=180): seq 2-3 get 60, seq 4-5 get 180.
        seq 1 (before the first update) is excluded."""
        stops = [
            _static_stop("A", 1, _BASE + timedelta(minutes=0)),
            _static_stop("B", 2, _BASE + timedelta(minutes=5)),
            _static_stop("C", 3, _BASE + timedelta(minutes=10)),
            _static_stop("D", 4, _BASE + timedelta(minutes=15)),
            _static_stop("E", 5, _BASE + timedelta(minutes=20)),
        ]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=2, arrival_delay=60, departure_delay=60
                ),
                SeptaRailStopUpdate(
                    stop_sequence=4, arrival_delay=180, departure_delay=180
                ),
            ]
        )

        arrivals = resolve_arrivals(trip, stops)
        by_code = {a.station_code: a for a in arrivals}

        assert "A" not in by_code, "seq 1 precedes the first update → excluded"
        assert by_code["B"].delay_seconds == 60
        assert by_code["C"].delay_seconds == 60  # propagated from seq 2
        assert by_code["D"].delay_seconds == 180
        assert by_code["E"].delay_seconds == 180  # propagated from seq 4
        assert by_code["C"].arrival_time == _BASE + timedelta(minutes=10, seconds=60)
        assert by_code["E"].arrival_time == _BASE + timedelta(minutes=20, seconds=180)

    def test_updates_out_of_order_are_sorted(self):
        """The first RT sequence is the smallest even if updates arrive unsorted."""
        stops = [
            _static_stop("A", 1, _BASE),
            _static_stop("B", 2, _BASE + timedelta(minutes=5)),
            _static_stop("C", 3, _BASE + timedelta(minutes=10)),
        ]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=3, arrival_delay=300, departure_delay=300
                ),
                SeptaRailStopUpdate(
                    stop_sequence=1, arrival_delay=60, departure_delay=60
                ),
            ]
        )

        arrivals = resolve_arrivals(trip, stops)
        by_code = {a.station_code: a for a in arrivals}
        # first_rt_seq must be 1, so no stop is excluded.
        assert set(by_code) == {"A", "B", "C"}
        assert by_code["A"].delay_seconds == 60
        assert by_code["B"].delay_seconds == 60  # propagated
        assert by_code["C"].delay_seconds == 300

    def test_departure_delay_fallback_when_arrival_delay_none(self):
        """When arrival_delay is None the applicable departure_delay is used for arrival."""
        stops = [
            _static_stop("A", 1, _BASE + timedelta(minutes=0)),
            _static_stop("B", 2, _BASE + timedelta(minutes=5)),
        ]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=1, arrival_delay=None, departure_delay=90
                )
            ]
        )

        arrivals = resolve_arrivals(trip, stops)
        assert all(a.delay_seconds == 90 for a in arrivals)
        assert arrivals[0].arrival_time == _BASE + timedelta(seconds=90)

    def test_arrival_delay_used_for_departure_when_departure_none(self):
        """When departure_delay is None the departure_time falls back to arrival delay."""
        stops = [
            _static_stop(
                "A",
                1,
                arrival=_BASE,
                departure=_BASE + timedelta(minutes=1),
            ),
        ]
        # Single-stop trips are legal for resolve_arrivals (the >= 2 guard lives in
        # _process_trip, not here).
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=1, arrival_delay=45, departure_delay=None
                )
            ]
        )

        arrivals = resolve_arrivals(trip, stops)
        assert len(arrivals) == 1
        arr = arrivals[0]
        assert arr.delay_seconds == 45
        assert arr.arrival_time == _BASE + timedelta(seconds=45)
        # departure_time = scheduled departure (base + 1min) + arrival-delay fallback (45s)
        assert arr.departure_time == _BASE + timedelta(minutes=1, seconds=45)

    def test_exact_timedelta_equality(self):
        """arrival_time is exactly static arrival + timedelta(seconds=delay)."""
        static_arr = ET.localize(datetime(2026, 7, 18, 14, 23, 7))
        stops = [_static_stop("Z", 1, static_arr)]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=1, arrival_delay=137, departure_delay=137
                )
            ]
        )
        arrivals = resolve_arrivals(trip, stops)
        assert arrivals[0].arrival_time == static_arr + timedelta(seconds=137)

    def test_empty_updates_returns_empty(self):
        assert resolve_arrivals(_trip([]), [_static_stop("A", 1, _BASE)]) == []

    def test_stop_with_none_sequence_is_skipped(self):
        """A static stop with a NULL stop_sequence cannot be positioned → skipped."""
        stops = [
            _static_stop("A", 1, _BASE),
            _static_stop("NULLSEQ", None, _BASE + timedelta(minutes=3)),
            _static_stop("B", 2, _BASE + timedelta(minutes=5)),
        ]
        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=60, departure_delay=60)]
        )
        arrivals = resolve_arrivals(trip, stops)
        assert [a.station_code for a in arrivals] == ["A", "B"]

    def test_carries_trip_identity_onto_arrivals(self):
        """route_id/direction_id/trip_id/track are copied through to each arrival."""
        stops = [_static_stop("A", 1, _BASE)]
        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=1, arrival_delay=10, departure_delay=10
                )
            ],
            trip_id="TRE9_20260718_SIDX",
            route_id="TRE",
            direction_id=1,
        )
        arr = resolve_arrivals(trip, stops)[0]
        assert isinstance(arr, SeptaRailArrival)
        assert arr.trip_id == "TRE9_20260718_SIDX"
        assert arr.route_id == "TRE"
        assert arr.direction_id == 1
        assert arr.track is None


class TestCollectorInit:
    def test_creates_own_client(self):
        collector = SeptaRailCollector()
        assert collector.client is not None
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        client = SeptaRailClient()
        collector = SeptaRailCollector(client=client)
        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_owned_client(self):
        collector = SeptaRailCollector()
        collector.client = AsyncMock(spec=SeptaRailClient)
        collector._owns_client = True
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client_not_closed(self):
        client = AsyncMock(spec=SeptaRailClient)
        collector = SeptaRailCollector(client=client)
        await collector.close()
        client.close.assert_not_called()


class TestProcessTrip:
    """_process_trip: the static schedule is mandatory for Regional Rail."""

    @pytest.fixture
    def collector(self):
        return SeptaRailCollector(client=AsyncMock(spec=SeptaRailClient))

    @pytest.mark.asyncio
    async def test_skips_when_no_static_schedule(self, collector):
        """No GTFS static schedule on today or yesterday → counted skip signal."""
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=[])
        session = AsyncMock()

        trip = _trip(
            [SeptaRailStopUpdate(stop_sequence=1, arrival_delay=60, departure_delay=60)]
        )
        result, journey = await collector._process_trip(session, trip)
        assert result == "skipped_no_static"
        assert journey is None

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_rr.collector.now_et")
    async def test_discovers_new_journey_from_delays(self, mock_now, collector):
        """End-to-end discovery: delays + static schedule → a new OBSERVED journey
        with a complete, back-filled stop list."""
        mock_now.return_value = _BASE

        static_stops = [
            _static_stop("SEPR90801", 1, _BASE + timedelta(minutes=0)),
            _static_stop("SEPR90802", 2, _BASE + timedelta(minutes=5)),
            _static_stop("SEPR90803", 3, _BASE + timedelta(minutes=10)),
            _static_stop("SEPR90804", 4, _BASE + timedelta(minutes=15)),
        ]
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(
            return_value=static_stops
        )

        # No existing journey for this train/day.
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute.return_value = no_existing

        trip = _trip(
            [
                SeptaRailStopUpdate(
                    stop_sequence=2, arrival_delay=120, departure_delay=120
                )
            ]
        )

        result, journey = await collector._process_trip(session, trip)

        assert result == "discovered"
        assert journey is not None
        assert journey.data_source == "SEPTA_RR"
        assert journey.train_id == "CHW8312"
        assert journey.observation_type == "OBSERVED"
        # A journey + one stop per merged static stop were added to the session.
        assert session.add.call_count >= 1
