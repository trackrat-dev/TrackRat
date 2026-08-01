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

2. **The cause.** When cancellations *do* legitimately escalate a segment,
   ``congestion_cause`` says so, distinguishing "cancellations" (the running
   trains were fine) from "both" (already delayed, pushed further). Without it
   the API reports ``congestion_level="severe"`` next to
   ``average_delay_minutes=0.0`` and every client renders "Severe delays" over
   an "On time" caption; with only a boolean, a genuinely delayed segment that
   cancellations escalated one more tier would have its real delay contradicted.

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
    CONGESTION_CAUSE_BOTH,
    CONGESTION_CAUSE_CANCELLATIONS,
    CONGESTION_CAUSE_DELAYS,
    SegmentCongestion,
    congestion_level_and_cause,
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


class TestCongestionLevelAndCause:
    """The tier, and whether cancellations rather than delays produced it."""

    def test_on_time_segment_with_heavy_cancellations_reports_cancellations(self):
        """10 journeys, half cancelled, running trains on time: escalated to
        severe and attributed to cancellations, because captioning this as
        "delays" would be false."""
        level, cause = congestion_level_and_cause(1.0, 50.0, 10, 0.0)
        assert level == "severe"
        assert cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_sparse_segment_is_neither_escalated_nor_attributed(self):
        """The #1638 case end-to-end through the tier helper: below the floor
        the segment stays normal, and the cause stays "delays" because the
        cancellations moved nothing."""
        level, cause = congestion_level_and_cause(1.0, 50.0, 2, 0.0)
        assert level == "normal"
        assert cause == CONGESTION_CAUSE_DELAYS

    def test_genuinely_delayed_segment_reports_delays(self):
        """A segment already severe on delays alone is a delay problem, and
        cancellations that cannot push it higher change nothing — this is the
        case the cause most easily over-reports if computed from the rate."""
        level, cause = congestion_level_and_cause(2.0, 50.0, 10, 12.0)
        assert level == "severe"
        assert cause == CONGESTION_CAUSE_DELAYS

    def test_cause_is_set_whenever_the_tier_moves_at_all(self):
        """Escalation by one tier counts, not just escalation to severe: 1.05
        (normal) + 20% * 0.015 = 1.35 -> heavy. The running trains lost only
        half a minute — below the map's own reporting floor — so this is a pure
        cancellation escalation."""
        level, cause = congestion_level_and_cause(1.05, 20.0, 10, 0.5)
        assert level == "heavy"
        assert cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_delayed_segment_escalated_further_reports_both(self):
        """The case a boolean flag cannot express (raised in review of #1681):
        1.2 is already moderate on delays alone, and a 20% rate over 10 journeys
        pushes it to heavy (1.2 + 20 * 0.015 = 1.5). Reporting this as
        "cancellations" would make clients drop a real +N min delay and caption
        the segment as if its trains ran on time; reporting it as "delays" would
        hide the cancellations. Both are true, so both must be said."""
        level, cause = congestion_level_and_cause(1.2, 20.0, 10, 4.0)
        assert level == "heavy"
        assert cause == CONGESTION_CAUSE_BOTH

    def test_reportable_delay_inside_the_normal_tier_still_reports_both(self):
        """The residual of the same defect, one tier lower: a long segment can
        carry a real delay without leaving the normal tier, because the factor
        is a ratio. 42 min against a 40 min baseline is 1.05 — normal — while
        the delay is a reportable +2.0 min, and 20% cancellations take the tier
        to heavy.

        Judging "were there delays?" by the tier alone would call this
        "cancellations", and the clients would then do exactly what the review
        objected to: the web drops it from delayedCount and iOS captions it
        "Heavy cancellations", both directly beside the "+2m" the very same row
        renders. The delay is judged by the map's absolute floor instead."""
        level, cause = congestion_level_and_cause(1.05, 20.0, 10, 2.0)
        assert level == "heavy"
        assert cause == CONGESTION_CAUSE_BOTH

    def test_mixed_cause_survives_the_sparse_floor(self):
        """Below the floor the cancellations are discarded, so a delayed segment
        is attributed to delays alone rather than to "both"."""
        level, cause = congestion_level_and_cause(1.2, 20.0, 2, 4.0)
        assert level == "moderate"
        assert cause == CONGESTION_CAUSE_DELAYS

    def test_noise_floored_delay_does_not_make_the_cause_mixed(self):
        """A sub-minute delay is jitter the map deliberately declines to show
        (MIN_CONGESTION_DELAY_MINUTES), so it must not make the cause "both" —
        that would have a client claim a delay nothing else renders."""
        level, cause = congestion_level_and_cause(1.0, 50.0, 10, 0.5)
        assert level == "severe"
        assert cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_delay_exactly_at_the_reporting_floor_counts_as_a_delay(self):
        """The boundary MIN_CONGESTION_DELAY_MINUTES is inclusive, matching
        reliable_congestion_factor, which keeps the real factor at exactly the
        floor rather than flattening it."""
        level, cause = congestion_level_and_cause(1.05, 20.0, 10, 1.0)
        assert level == "heavy"
        assert cause == CONGESTION_CAUSE_BOTH

    def test_early_running_segment_is_not_called_delayed(self):
        """A segment running 2 min *early* clears an absolute floor but has no
        delay to name. Both clients render a delay only when it is positive, so
        "both" would put this in the web's delayed count with no "+Nm" beside
        it — the same contradiction, mirrored. The comparison is signed."""
        level, cause = congestion_level_and_cause(1.05, 20.0, 10, -2.0)
        assert level == "heavy"
        assert cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_cancellations_too_small_to_move_the_tier_report_delays(self):
        """A rate that clears the floor but does not cross a threshold leaves
        the tier alone, so there is nothing to relabel."""
        level, cause = congestion_level_and_cause(1.0, 5.0, 10, 0.0)
        assert level == "normal"
        assert cause == CONGESTION_CAUSE_DELAYS


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
        assert seg.congestion_cause == CONGESTION_CAUSE_DELAYS

    def test_sustained_cancellations_still_escalate_and_are_attributed(self):
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
        assert seg.congestion_cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_floor_counts_cancellations_toward_the_journey_total(self):
        """The denominator is running + cancelled, so an all-but-one-cancelled
        segment can clear the floor on cancellations alone. 1 running + 4
        cancelled = 5 journeys at an 80% rate."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=1, cancellation_count=4)]
        )
        assert len(result) == 1
        assert result[0].congestion_level == "severe"
        assert result[0].congestion_cause == CONGESTION_CAUSE_CANCELLATIONS

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
        assert seg.congestion_cause == CONGESTION_CAUSE_CANCELLATIONS

    def test_sparse_but_genuinely_delayed_segment_still_escalates(self):
        """The floor must not become a general "too few trains" mute. Two
        journeys, one cancelled, but the train that ran lost 5 minutes: that is
        a real delay and stays severe — attributed to delays, not cancellations."""
        result = normalize_aggregated_segments(
            [_seg(sample_count=1, cancellation_count=1, avg_transit=10.0, baseline=5.0)]
        )
        assert len(result) == 1
        seg = result[0]
        assert seg.average_delay_minutes == pytest.approx(5.0)
        assert seg.congestion_level == "severe"
        assert seg.congestion_cause == CONGESTION_CAUSE_DELAYS


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
        assert seg.congestion_cause == CONGESTION_CAUSE_DELAYS

    async def test_sustained_cancellations_still_render_severe(
        self, db_session: AsyncSession
    ):
        """The #1246 signal survives: enough journeys to trust, half of them
        cancelled, running trains on time -> severe, attributed to cancellations
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
        assert seg.congestion_cause == CONGESTION_CAUSE_CANCELLATIONS
