"""Tests for the minimum-sample floor on cancellation-driven congestion (#1638).

Reported symptom: an NJ Transit North Jersey Coast Line segment (South Amboy ->
Perth Amboy) rendered red on the congestion map while the delay statistics
beside it read zero. That is not a glitch — it is arithmetic. Cancellations are
folded into the level (#1246) at ``CANCELLATION_CONGESTION_WEIGHT = 0.015`` per
percent, and the rate is ``cancelled / (running + cancelled)``. On an off-peak
stretch running 1-2 trains/hour, one cancellation against one running train is
50%, which alone clears the severe threshold (1.0 + 50 * 0.015 = 1.75) with
every train that ran exactly on time.

Two things are asserted here:

1. **The floor.** Below ``CANCELLATION_MIN_JOURNEYS`` scheduled journeys the
   cancellation term is dropped entirely, so a sparse segment can no longer be
   painted red by a single cancellation. The delay component is never gated —
   a genuinely slow sparse segment must still escalate on its own merits.

2. **The cause flag.** When cancellations *do* legitimately escalate a segment,
   ``cancellation_driven`` is set so clients can caption it truthfully. Without
   it the API reports ``congestion_level="severe"`` next to
   ``average_delay_minutes=0.0`` and every client renders "Severe delays" over
   an "On time" caption.

The pure-function and normalizer tests are deterministic; the real-DB tests
drive the optimized SQL path that production actually serves, against real
PostgreSQL with no substituted services.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.services.congestion_types import (
    CANCELLATION_MIN_JOURNEYS,
    SegmentCongestion,
    congestion_level_with_cancellations,
    effective_congestion_factor,
)
from trackrat.services.segment_normalizer import normalize_aggregated_segments
from trackrat.utils.time import now_et

# The reported segment: adjacent NJT North Jersey Coast Line stations.
SOUTH_AMBOY = "CH"
PERTH_AMBOY = "PE"


class TestEffectiveCongestionFactorFloor:
    """The cancellation term is applied only when the sample supports it."""

    def test_omitting_total_journeys_leaves_arithmetic_unchanged(self):
        """The floor is opt-in: callers that genuinely have no journey count
        still get the raw blend, so the pure weighting stays testable."""
        assert effective_congestion_factor(1.0, 50.0) == pytest.approx(1.75)
        assert effective_congestion_factor(1.0, 50.0, None) == pytest.approx(1.75)

    def test_one_cancellation_against_one_train_is_ignored(self):
        """The exact #1638 shape: 2 journeys, one cancelled. A 50% rate over two
        journeys is not evidence of anything, so the factor must not move."""
        assert effective_congestion_factor(1.0, 50.0, 2) == pytest.approx(1.0)

    def test_floor_boundary_is_inclusive(self):
        """At exactly CANCELLATION_MIN_JOURNEYS the rate counts; one below it
        does not. Pinning both sides so the boundary cannot drift silently."""
        below = CANCELLATION_MIN_JOURNEYS - 1
        assert effective_congestion_factor(1.0, 40.0, below) == pytest.approx(1.0)
        assert effective_congestion_factor(
            1.0, 40.0, CANCELLATION_MIN_JOURNEYS
        ) == pytest.approx(1.6)

    def test_delay_component_survives_the_floor(self):
        """The floor drops cancellations, never delays. A sparse segment whose
        trains genuinely lost time keeps its full factor — suppressing that
        would hide real problems on exactly the low-frequency stretches riders
        most need warning about."""
        assert effective_congestion_factor(1.8, 50.0, 1) == pytest.approx(1.8)

    def test_negative_rate_still_clamped_above_the_floor(self):
        """Clamping and gating compose: a nonsense negative rate never reduces
        the factor even when the journey count clears the floor."""
        assert effective_congestion_factor(1.2, -5.0, 20) == pytest.approx(1.2)


class TestCongestionLevelWithCancellations:
    """The tier, and whether cancellations rather than delays produced it."""

    def test_on_time_segment_with_heavy_cancellations_is_flagged(self):
        """10 journeys, half cancelled, running trains on time: escalated to
        severe and flagged, because captioning this "delays" would be false."""
        level, driven = congestion_level_with_cancellations(1.0, 50.0, 10)
        assert level == "severe"
        assert driven is True

    def test_sparse_segment_is_neither_escalated_nor_flagged(self):
        """The #1638 case end-to-end through the tier helper: below the floor
        the segment stays normal, and nothing is flagged because nothing moved."""
        level, driven = congestion_level_with_cancellations(1.0, 50.0, 2)
        assert level == "normal"
        assert driven is False

    def test_genuinely_delayed_segment_is_not_flagged(self):
        """A segment already severe on delays alone is a delay problem. The flag
        must stay False so clients keep saying "delays" — this is the case the
        flag most easily over-reports if it were computed from the rate alone."""
        level, driven = congestion_level_with_cancellations(2.0, 50.0, 10)
        assert level == "severe"
        assert driven is False

    def test_flag_is_set_whenever_the_tier_moves_at_all(self):
        """Escalation by one tier counts, not just escalation to severe: 1.05
        (normal) + 20% * 0.015 = 1.35 -> heavy."""
        level, driven = congestion_level_with_cancellations(1.05, 20.0, 10)
        assert level == "heavy"
        assert driven is True

    def test_cancellations_too_small_to_move_the_tier_are_not_flagged(self):
        """A rate that clears the floor but does not cross a threshold leaves
        the tier alone, so there is nothing to relabel."""
        level, driven = congestion_level_with_cancellations(1.0, 5.0, 10)
        assert level == "normal"
        assert driven is False


def _seg(
    *,
    sample_count: int,
    cancellation_count: int,
    avg_transit: float = 5.0,
    baseline: float = 5.0,
) -> SegmentCongestion:
    """A raw pre-normalization segment on an adjacent NJT pair (not expanded)."""
    return SegmentCongestion(
        from_station=SOUTH_AMBOY,
        to_station=PERTH_AMBOY,
        data_source="NJT",
        congestion_factor=avg_transit / baseline,
        congestion_level="severe",  # input ignored; recomputed by the normalizer
        avg_transit_minutes=avg_transit,
        baseline_minutes=baseline,
        sample_count=sample_count,
        average_delay_minutes=avg_transit - baseline,
        cancellation_count=cancellation_count,
    )


class TestNormalizerCancellationFloor:
    """The re-aggregation path applies the same floor and sets the flag."""

    def test_one_cancelled_one_running_stays_normal(self):
        """The reported scenario. Before the floor this produced a 50% rate and
        a severe (red) segment with an average delay of zero."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=1, cancellation_count=1)]
        )
        assert len(result) == 1
        seg = result[0]
        assert seg.cancellation_rate == pytest.approx(50.0)
        assert seg.average_delay_minutes == pytest.approx(0.0)
        assert seg.congestion_level == "normal"
        assert seg.cancellation_driven is False

    def test_sustained_cancellations_still_escalate_and_are_flagged(self):
        """The #1246 behavior this floor must not break: a segment with enough
        journeys to trust still turns red on cancellations alone."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=5, cancellation_count=5)]
        )
        assert len(result) == 1
        seg = result[0]
        assert seg.cancellation_rate == pytest.approx(50.0)
        assert seg.congestion_factor == pytest.approx(1.0)
        assert seg.congestion_level == "severe"
        assert seg.cancellation_driven is True

    def test_floor_counts_cancellations_toward_the_journey_total(self):
        """The denominator is running + cancelled, so an all-but-one-cancelled
        segment can clear the floor on cancellations alone. 1 running + 4
        cancelled = 5 journeys at an 80% rate."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=1, cancellation_count=4)]
        )
        assert len(result) == 1
        assert result[0].congestion_level == "severe"
        assert result[0].cancellation_driven is True

    def test_sparse_segments_aggregate_over_the_floor(self):
        """Skip-stop expansion feeds several raw sub-segments into one canonical
        pair. Each below the floor individually, they must be judged on the sum
        — otherwise the floor would suppress a real signal after normalization."""
        result = normalize_aggregated_segments(
            [
                _seg(sample_count=1, cancellation_count=2),
                _seg(sample_count=1, cancellation_count=2),
            ]
        )
        assert len(result) == 1
        seg = result[0]
        assert seg.sample_count == 2
        assert seg.cancellation_count == 4
        assert seg.congestion_level == "severe"
        assert seg.cancellation_driven is True

    def test_sparse_but_genuinely_delayed_segment_still_escalates(self):
        """The floor must not become a general "too few trains" mute. Two
        journeys, one cancelled, but the train that ran lost 5 minutes: that is
        a real delay and stays severe — flagged as delays, not cancellations."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=1, cancellation_count=1, avg_transit=10.0, baseline=5.0)]
        )
        assert len(result) == 1
        seg = result[0]
        assert seg.average_delay_minutes == pytest.approx(5.0)
        assert seg.congestion_level == "severe"
        assert seg.cancellation_driven is False


async def _add_njt_journey(
    db: AsyncSession,
    train_id: str,
    *,
    departure: datetime,
    transit_minutes: float,
    scheduled_minutes: float,
    is_cancelled: bool = False,
) -> None:
    """Create a two-stop NJT journey on the reported South Amboy -> Perth Amboy
    segment. A cancelled journey carries its scheduled times and no actuals,
    which is how the collectors record one — the congestion query windows it on
    ``from_scheduled_departure`` for exactly that reason.
    """
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        line_code="NC",
        line_name="North Jersey Coast Line",
        destination=PERTH_AMBOY,
        origin_station_code=SOUTH_AMBOY,
        terminal_station_code=PERTH_AMBOY,
        data_source="NJT",
        observation_type="SCHEDULED" if is_cancelled else "OBSERVED",
        scheduled_departure=departure,
        is_cancelled=is_cancelled,
        has_complete_journey=not is_cancelled,
        stops_count=2,
    )
    db.add(journey)
    await db.flush()

    db.add(
        JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code=SOUTH_AMBOY,
            station_name="South Amboy",
            stop_sequence=1,
            scheduled_departure=departure,
            actual_departure=None if is_cancelled else departure,
        )
    )
    db.add(
        JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code=PERTH_AMBOY,
            station_name="Perth Amboy",
            stop_sequence=2,
            scheduled_arrival=departure + timedelta(minutes=scheduled_minutes),
            actual_arrival=(
                None if is_cancelled else departure + timedelta(minutes=transit_minutes)
            ),
        )
    )
    await db.flush()


async def _segment(db: AsyncSession) -> SegmentCongestion | None:
    analyzer = CongestionAnalyzer()
    segments = await analyzer.get_network_congestion_optimized(
        db, time_window_hours=3, data_source="NJT"
    )
    return next(
        (
            s
            for s in segments
            if (s.from_station, s.to_station) == (SOUTH_AMBOY, PERTH_AMBOY)
        ),
        None,
    )


@pytest.mark.asyncio
class TestCancellationFloorRealDB:
    """End-to-end through the optimized SQL path against real PostgreSQL."""

    async def test_reported_scenario_renders_normal(self, db_session: AsyncSession):
        """#1638 as reported: one on-time train and one cancelled train on an
        off-peak NJCL segment must not paint it red."""
        dep = now_et() - timedelta(minutes=30)
        await _add_njt_journey(
            db_session,
            "njt_ran",
            departure=dep,
            transit_minutes=6,
            scheduled_minutes=6,
        )
        await _add_njt_journey(
            db_session,
            "njt_cancelled",
            departure=dep + timedelta(minutes=5),
            transit_minutes=6,
            scheduled_minutes=6,
            is_cancelled=True,
        )
        await db_session.commit()

        seg = await _segment(db_session)
        assert seg is not None, "the CH->PE segment should still be reported"
        assert seg.cancellation_count == 1
        assert seg.cancellation_rate == pytest.approx(50.0)
        assert seg.average_delay_minutes == pytest.approx(0.0, abs=0.05)
        assert seg.congestion_level == "normal", (
            "a single cancellation on a sparse segment must not render severe "
            "while every train that ran was on time (#1638)"
        )
        assert seg.cancellation_driven is False

    async def test_sustained_cancellations_still_render_severe(
        self, db_session: AsyncSession
    ):
        """The #1246 signal survives: enough journeys to trust, half of them
        cancelled, running trains on time -> severe and flagged as cancellations
        so no client captions it as a delay."""
        dep = now_et() - timedelta(minutes=30)
        for i in range(4):
            await _add_njt_journey(
                db_session,
                f"njt_ok_{i}",
                departure=dep + timedelta(minutes=i),
                transit_minutes=6,
                scheduled_minutes=6,
            )
        for i in range(4):
            await _add_njt_journey(
                db_session,
                f"njt_cxl_{i}",
                departure=dep + timedelta(minutes=10 + i),
                transit_minutes=6,
                scheduled_minutes=6,
                is_cancelled=True,
            )
        await db_session.commit()

        seg = await _segment(db_session)
        assert seg is not None
        assert seg.cancellation_count == 4
        assert seg.cancellation_rate == pytest.approx(50.0)
        assert seg.average_delay_minutes == pytest.approx(0.0, abs=0.05)
        assert seg.congestion_level == "severe"
        assert seg.cancellation_driven is True
