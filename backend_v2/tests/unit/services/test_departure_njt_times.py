"""
Unit tests for DepartureService._effective_updated_time (issue #1505).

The departure boards computed the from-stop's live time with an inline,
unconditional max(updated_departure, updated_arrival) — the NJT inversion
correction, but WITHOUT the #1492 terminal exemption and duplicated apart
from the canonical utils/train helpers. When an NJT journey's terminal stop
landed on a station board (a terminating train in recent-departures), the
max() promoted the turnaround DEP_TIME over the live arrival TIME — the
exact inflation #1492 fixed for /trains/{id} and share previews — and those
values were cached (120s TTL + precompute).

_effective_updated_time now routes both boards through
effective_njt_updated_times + terminal_stop_index, so the correction has a
single implementation. _effective_updated_arrival (issue #1527) is its twin
for the destination stop's arrival block, which was the last spot on this
path still reading the raw pair. Shared posture:
- intermediate NJT stop: max() surfaces the live delayed estimate;
- genuine terminal (fully-sequenced journey whose last stop matches
  terminal_station_code): live arrival, never the turnaround departure;
- partially-collected journey (NULL sequences / placeholder terminal):
  conservatively keeps the max();
- non-NJT providers: raw estimates pass through.
"""

from datetime import timedelta

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _journey(data_source: str = "NJT", terminal: str = "NY") -> TrainJourney:
    return TrainJourney(
        train_id="3922",
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="PJ",
        terminal_station_code=terminal,
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=now_et() - timedelta(hours=1),
        has_complete_journey=True,
    )


def _stops(schedule, live, terminal_dep_time=None, sequenced=True):
    """PJ (origin) -> SE (intermediate) -> NY (terminal).

    SE and NY carry NJT's raw inverted fields. terminal_dep_time simulates
    NJT populating the terminal's DEP_TIME with a later turnaround
    departure (the #1492 trigger).
    """
    return [
        JourneyStop(
            station_code="PJ",
            station_name="Princeton Junction",
            stop_sequence=0 if sequenced else None,
            scheduled_departure=schedule,
            has_departed_station=True,
        ),
        JourneyStop(
            station_code="SE",
            station_name="Secaucus Upper Lvl",
            stop_sequence=5 if sequenced else None,
            scheduled_departure=schedule + timedelta(minutes=40),
            updated_departure=schedule + timedelta(minutes=40),  # DEP_TIME = sched
            updated_arrival=live + timedelta(minutes=40),  # TIME = live
            has_departed_station=False,
        ),
        JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=10 if sequenced else None,
            scheduled_arrival=schedule + timedelta(minutes=55),
            updated_arrival=live + timedelta(minutes=55),  # TIME = live arrival
            updated_departure=terminal_dep_time,  # DEP_TIME = turnaround
            has_departed_station=False,
        ),
    ]


class TestEffectiveUpdatedTime:
    def test_intermediate_njt_stop_surfaces_live_delayed_estimate(self):
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=15)  # 15-min delay

        journey = _journey()
        stops = _stops(schedule, live)

        updated = DepartureService._effective_updated_time(journey, stops[1], stops)
        assert updated == live + timedelta(minutes=40), (
            "Intermediate NJT stop must surface the live delayed estimate "
            "(max of the inverted pair), not the schedule"
        )

    def test_terminal_njt_stop_shows_live_arrival_not_turnaround(self):
        """The #1492 case on a departure board: NJT populates the terminal's
        DEP_TIME with a later turnaround departure. An on-time train's board
        entry must show its live arrival, not the turnaround time.
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule  # on time
        turnaround = schedule + timedelta(minutes=70)  # later turnaround DEP

        journey = _journey()
        stops = _stops(schedule, live, terminal_dep_time=turnaround)

        updated = DepartureService._effective_updated_time(journey, stops[2], stops)
        assert updated == live + timedelta(minutes=55), (
            "Terminal stop must show the live arrival (TIME); the max() "
            "would promote the turnaround DEP_TIME and inflate the "
            "displayed time (issue #1492 / #1505)"
        )

    def test_partially_collected_journey_keeps_conservative_max(self):
        """With NULL sequences (placeholder rows before full collection),
        positional terminal detection can't be trusted — the last-sorted
        stop keeps the max() so a real intermediate delay is never hidden.
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=15)
        turnaround = schedule + timedelta(minutes=70)

        journey = _journey()
        stops = _stops(schedule, live, terminal_dep_time=turnaround, sequenced=False)

        updated = DepartureService._effective_updated_time(journey, stops[2], stops)
        assert updated == max(turnaround, live + timedelta(minutes=55)), (
            "Unsequenced journeys must conservatively keep the max() — "
            "the same posture as terminal_stop_index"
        )

    def test_placeholder_terminal_station_code_keeps_conservative_max(self):
        """Sequenced stops but a terminal_station_code that doesn't match the
        last stop (discovery placeholder) must also decline the exemption.
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=15)
        turnaround = schedule + timedelta(minutes=70)

        journey = _journey(terminal="PJ")  # placeholder: discovery station
        stops = _stops(schedule, live, terminal_dep_time=turnaround)

        updated = DepartureService._effective_updated_time(journey, stops[2], stops)
        assert updated == max(turnaround, live + timedelta(minutes=55))

    def test_non_njt_provider_uses_raw_departure_estimate(self):
        schedule = now_et() - timedelta(minutes=50)

        journey = _journey(data_source="LIRR")
        stops = _stops(schedule, schedule)
        # Genuine live estimates for LIRR: arrival later than departure —
        # a max() would wrongly pick the arrival.
        stops[1].updated_departure = schedule + timedelta(minutes=40)
        stops[1].updated_arrival = schedule + timedelta(minutes=43)

        updated = DepartureService._effective_updated_time(journey, stops[1], stops)
        assert updated == schedule + timedelta(
            minutes=40
        ), "Non-NJT providers keep their genuine updated_departure estimate"

    def test_single_field_falls_back_across_pair(self):
        """When only one of the pair is populated, it is used regardless of
        which slot it sits in (matches the old or-chain behavior).
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=15)

        journey = _journey()
        stops = _stops(schedule, live)
        stops[1].updated_departure = None  # only TIME present

        updated = DepartureService._effective_updated_time(journey, stops[1], stops)
        assert updated == live + timedelta(minutes=40)


class TestEffectiveUpdatedArrival:
    """Destination-stop arrival twin (issue #1527)."""

    def test_intermediate_njt_arrival_surfaces_live_delayed_estimate(self):
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=9)  # the reported 9-min slip

        journey = _journey()
        stops = _stops(schedule, live)

        updated = DepartureService._effective_updated_arrival(journey, stops[1], stops)
        assert updated == live + timedelta(minutes=40), (
            "An intermediate NJT destination must surface the live delayed "
            "arrival estimate (TIME), letting clients show the en-route slip"
        )

    def test_intermediate_njt_arrival_clamps_early_time_to_schedule(self):
        """The behavioral delta vs the old raw or-chain: a nominally-early
        TIME at an intermediate stop is clamped to the DEP_TIME schedule by
        the canonical max(), matching the SQL twin and the departure block.
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule - timedelta(minutes=5)  # TIME runs ahead of schedule

        journey = _journey()
        stops = _stops(schedule, live)

        updated = DepartureService._effective_updated_arrival(journey, stops[1], stops)
        assert updated == schedule + timedelta(minutes=40), (
            "Canonical max() must clamp an early TIME to the DEP_TIME "
            "schedule at intermediate stops; the raw or-chain leaked TIME"
        )

    def test_terminal_njt_arrival_shows_live_arrival_not_turnaround(self):
        """#1492 exemption on the arrival block: the terminal's DEP_TIME can
        be a later turnaround departure and must never be shown as arrival.
        """
        schedule = now_et() - timedelta(minutes=50)
        live = schedule  # on time
        turnaround = schedule + timedelta(minutes=70)

        journey = _journey()
        stops = _stops(schedule, live, terminal_dep_time=turnaround)

        updated = DepartureService._effective_updated_arrival(journey, stops[2], stops)
        assert updated == live + timedelta(minutes=55), (
            "Terminal destination must show the live arrival (TIME); the "
            "max() would promote the turnaround DEP_TIME (issue #1492)"
        )

    def test_non_njt_arrival_prefers_genuine_arrival_estimate(self):
        schedule = now_et() - timedelta(minutes=50)

        journey = _journey(data_source="LIRR")
        stops = _stops(schedule, schedule)
        # Genuine live estimates for LIRR: arrival and dwell-end departure
        # legitimately differ; the arrival block must keep the arrival.
        stops[1].updated_arrival = schedule + timedelta(minutes=43)
        stops[1].updated_departure = schedule + timedelta(minutes=45)

        updated = DepartureService._effective_updated_arrival(journey, stops[1], stops)
        assert updated == schedule + timedelta(
            minutes=43
        ), "Non-NJT providers keep their genuine updated_arrival estimate"

    def test_arrival_single_field_falls_back_across_pair(self):
        schedule = now_et() - timedelta(minutes=50)
        live = schedule + timedelta(minutes=15)

        journey = _journey()
        stops = _stops(schedule, live)
        stops[1].updated_arrival = None  # only DEP_TIME present

        updated = DepartureService._effective_updated_arrival(journey, stops[1], stops)
        assert updated == schedule + timedelta(minutes=40), (
            "With only one field populated it is used regardless of slot "
            "(matches the old or-chain behavior)"
        )
