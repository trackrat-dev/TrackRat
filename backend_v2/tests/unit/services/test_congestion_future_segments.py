"""
Unit tests for the congestion segment window upper bound (issue #1603).

The congestion segment predicates windowed each stop pair on its own departure
time with a lower bound only (``>= :cutoff_time``). Amtrak writes non-null
``actual_arrival`` / ``actual_departure`` for stops the train has NOT yet
reached — schedule passthrough with delay 0 (``collectors/amtrak/journey.py``
sets ``actual_arrival``/``actual_departure`` unconditionally from the feed's
``arr``/``dep``, while the ``has_departed`` guard only gates the
``has_departed_station`` flag). Those future-timestamped rows sailed through the
lower bound and were counted, which:

  1. inflated ``train_count`` / ``frequency_factor`` for segments a
     long-distance train would not reach for hours (17 "trains" through
     Aberdeen in a 2h window), and
  2. injected fictitious on-time (delay-0) samples into ``avg_actual``.

The fix bounds each segment on the ARRIVAL: a segment is only counted once the
train has actually completed it (``to_arrival <= now``). Because arrival is
required to be after departure, this also bounds the departure to the past, so
one predicate closes both the fully-future phantom segments and the in-progress
segment whose downstream stop carries a future passthrough arrival.

Both consumption paths are covered:
- the SQL segment queries (``get_individual_segments_optimized`` and
  ``get_network_congestion_optimized``), exercised against real PostgreSQL, and
- the Python fallback path (``_calculate_segments_from_journeys``).

Stations WI -> ABE -> BL -> BA are consecutive on the Amtrak NEC topology, so
every segment survives ``normalize_*_segments`` (AMTRAK requires a route match)
and the assertions reflect the SQL predicate rather than normalization drops.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.utils.time import now_et


def _mid_journey_amtrak() -> TrainJourney:
    """An Amtrak NEC train currently between ABE and BL (southbound).

    WI -> ABE is completed (both times in the past). BL and BA are not yet
    reached but carry future schedule-passthrough actual times (delay 0), so
    ABE -> BL (in-progress, future arrival) and BL -> BA (fully future) are the
    phantom segments the fix must exclude.
    """
    now = now_et().replace(microsecond=0)
    journey = TrainJourney(
        train_id="AMTRAK_99_1603",
        journey_date=now.date(),
        line_code="AM",
        line_name="Northeast Corridor",
        destination="Washington",
        origin_station_code="WI",
        terminal_station_code="BA",
        data_source="AMTRAK",
        observation_type="OBSERVED",
        scheduled_departure=now - timedelta(minutes=60),
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
        last_updated_at=now,
    )
    journey.stops = [
        # WI: departed 60 min ago (completed)
        JourneyStop(
            station_code="WI",
            station_name="Wilmington",
            stop_sequence=0,
            scheduled_departure=now - timedelta(minutes=60),
            actual_arrival=now - timedelta(minutes=62),
            actual_departure=now - timedelta(minutes=60),
            has_departed_station=True,
        ),
        # ABE: arrived/departed ~40 min ago (completes WI -> ABE)
        JourneyStop(
            station_code="ABE",
            station_name="Aberdeen",
            stop_sequence=1,
            scheduled_arrival=now - timedelta(minutes=40),
            scheduled_departure=now - timedelta(minutes=39),
            actual_arrival=now - timedelta(minutes=40),
            actual_departure=now - timedelta(minutes=39),
            has_departed_station=True,
        ),
        # BL: NOT yet reached — future schedule-passthrough actuals (delay 0)
        JourneyStop(
            station_code="BL",
            station_name="Baltimore",
            stop_sequence=2,
            scheduled_arrival=now + timedelta(minutes=20),
            scheduled_departure=now + timedelta(minutes=21),
            actual_arrival=now + timedelta(minutes=20),
            actual_departure=now + timedelta(minutes=21),
            has_departed_station=False,
        ),
        # BA: NOT yet reached — future passthrough actuals
        JourneyStop(
            station_code="BA",
            station_name="BWI Airport",
            stop_sequence=3,
            scheduled_arrival=now + timedelta(minutes=45),
            actual_arrival=now + timedelta(minutes=45),
            actual_departure=now + timedelta(minutes=46),
            has_departed_station=False,
        ),
    ]
    return journey


class TestSqlSegmentWindowUpperBound:
    """The SQL segment predicates must exclude not-yet-completed segments."""

    @pytest.mark.asyncio
    async def test_individual_segments_excludes_future_stop_pairs(
        self, db_session: AsyncSession
    ):
        """Only the completed WI -> ABE segment is returned; the in-progress
        (ABE -> BL) and fully-future (BL -> BA) pairs are dropped."""
        journey = _mid_journey_amtrak()
        db_session.add(journey)
        await db_session.flush()
        db_session.add_all(journey.stops)
        await db_session.flush()

        analyzer = CongestionAnalyzer()
        segments = await analyzer.get_individual_segments_optimized(
            db_session,
            time_window_hours=3,
            max_per_segment=100,
            data_source="AMTRAK",
        )

        mine = [s for s in segments if str(s.journey_id) == str(journey.id)]
        pairs = {(s.from_station, s.to_station) for s in mine}

        assert pairs == {("WI", "ABE")}, (
            "Only the completed WI->ABE segment should be counted; got "
            f"{sorted(pairs)}. ABE->BL / BL->BA carry future passthrough "
            "actual times and must be excluded (issue #1603)."
        )

        now = now_et()
        for s in mine:
            assert s.actual_arrival <= now, (
                f"Segment {s.from_station}->{s.to_station} has a future "
                f"arrival {s.actual_arrival} (now={now}); the window must only "
                "count completed segments."
            )

    @pytest.mark.asyncio
    async def test_aggregated_train_count_excludes_future_segments(
        self, db_session: AsyncSession
    ):
        """train_count / sample_count for the far-ahead segments must not be
        inflated by a train that has not reached them yet."""
        journey = _mid_journey_amtrak()
        db_session.add(journey)
        await db_session.flush()
        db_session.add_all(journey.stops)
        await db_session.flush()

        analyzer = CongestionAnalyzer()
        results = await analyzer.get_network_congestion_optimized(
            db_session, time_window_hours=3, data_source="AMTRAK"
        )

        by_pair = {(r.from_station, r.to_station): r for r in results}

        assert ("WI", "ABE") in by_pair, (
            "The completed WI->ABE segment should appear; got "
            f"{sorted(by_pair)}"
        )
        completed = by_pair[("WI", "ABE")]
        assert completed.train_count == 1
        assert completed.sample_count == 1

        assert ("ABE", "BL") not in by_pair, (
            "ABE->BL (train not yet arrived at BL) must not be counted — this "
            "is the far-ahead inflation from issue #1603."
        )
        assert ("BL", "BA") not in by_pair, (
            "BL->BA (fully in the future) must not be counted (issue #1603)."
        )


class TestPythonPathWindowUpperBound:
    """_calculate_segments_from_journeys must apply the same upper bound."""

    def test_excludes_future_and_in_progress_segments(self):
        analyzer = CongestionAnalyzer()
        cutoff = now_et() - timedelta(hours=3)

        journey = _mid_journey_amtrak()
        journey.id = 1

        segment_groups, _ = analyzer._calculate_segments_from_journeys(
            [journey], cutoff
        )

        assert ("WI", "ABE", "AMTRAK") in segment_groups, (
            f"Completed WI->ABE segment missing; got {list(segment_groups)}"
        )
        actual_minutes = segment_groups[("WI", "ABE", "AMTRAK")][0]["actual_minutes"]
        assert actual_minutes == pytest.approx(20.0, abs=0.01), (
            "WI->ABE transit time should be ~20 min (dep -60 to arr -40); "
            f"got {actual_minutes}"
        )

        assert ("ABE", "BL", "AMTRAK") not in segment_groups, (
            "ABE->BL has a future arrival at BL (not yet traversed) and must "
            "be excluded; without the upper bound it reports a bogus ~59-min "
            "transit time (issue #1603)."
        )
        assert ("BL", "BA", "AMTRAK") not in segment_groups, (
            "BL->BA is fully in the future and must be excluded (issue #1603)."
        )
