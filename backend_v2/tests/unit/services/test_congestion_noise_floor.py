"""Tests for the congestion noise floors that keep closely-spaced stops from
rendering as jarring "confetti".

Two guards are covered:

1. Delay noise floor (``reliable_congestion_factor``): a segment only counts as
   congested when trains lose >= ``MIN_CONGESTION_DELAY_MINUTES`` of absolute
   time. On SEPTA Metro trolley curb stops (~30-60s apart) the sub-minute
   scheduled baseline turned a few seconds of GTFS-RT rounding into
   heavy/severe segments; the floor suppresses that while leaving genuine
   multi-minute delays (and cancellation-driven escalation) untouched.

2. Frequency baseline floor (``frequency_is_reliable``): a per-segment
   frequency level is only assigned when the historical baseline reaches
   ``FREQ_MIN_BASELINE_TRAINS``. A tiny per-curb baseline otherwise makes ±1
   train flip healthy/moderate/reduced between adjacent stops. The observed
   count is NOT floored, so a real drop (few trains ran against a solid
   baseline) is still surfaced as severe/reduced.

The pure-function and normalizer-level tests are deterministic; the real-DB
tests prove the optimized SQL path (used in production) applies the delay
floor end-to-end.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.services.congestion_types import (
    FREQ_MIN_BASELINE_TRAINS,
    MIN_CONGESTION_DELAY_MINUTES,
    SegmentCongestion,
    frequency_is_reliable,
    reliable_congestion_factor,
)
from trackrat.services.segment_normalizer import normalize_aggregated_segments
from trackrat.utils.time import now_et


class TestReliableCongestionFactor:
    """Unit tests for the delay noise floor."""

    def test_sub_floor_positive_delay_clamped_to_nominal(self):
        """A 45s delay on a 45s baseline (factor 2.0) is noise -> nominal 1.0."""
        # 0.75 min actual over 0.75 min baseline delay => factor 2.0
        assert reliable_congestion_factor(2.0, 0.75) == 1.0

    def test_delay_at_floor_is_kept(self):
        """A delay exactly at the floor is real and keeps its factor."""
        assert reliable_congestion_factor(1.5, MIN_CONGESTION_DELAY_MINUTES) == 1.5

    def test_genuine_multi_minute_delay_preserved(self):
        """A stuck train losing several minutes stays escalated even on a short
        hop — the guard is about absolute lost time, not the ratio."""
        assert reliable_congestion_factor(4.0, 3.0) == 4.0

    def test_small_negative_delay_clamped(self):
        """A slightly-early train (small negative delay) is also nominal."""
        assert reliable_congestion_factor(0.6, -0.5) == 1.0

    def test_large_negative_delay_preserved(self):
        """A meaningfully-early train keeps its (sub-1.0) factor, still normal."""
        assert reliable_congestion_factor(0.4, -2.0) == 0.4


class TestFrequencyIsReliable:
    """Unit tests for the frequency sample floor."""

    def test_none_counts_are_unreliable(self):
        assert frequency_is_reliable(None, None) is False
        assert frequency_is_reliable(5, None) is False
        assert frequency_is_reliable(None, 5.0) is False

    def test_tiny_baseline_is_unreliable(self):
        """A tiny historical baseline (the denominator) is noise, regardless of
        the observed count."""
        assert frequency_is_reliable(2, 2.5) is False
        assert frequency_is_reliable(10, float(FREQ_MIN_BASELINE_TRAINS - 1)) is False

    def test_low_observed_against_solid_baseline_is_reliable(self):
        """A low observed count against a solid baseline is a REAL service drop,
        not noise, and must stay reliable so health mode surfaces it (a 2/20
        factor of 0.1 is severe). Regression guard for the observed-count floor.
        """
        assert frequency_is_reliable(2, 20.0) is True
        # Total service loss (0 trains ran) with a solid baseline is also real.
        assert frequency_is_reliable(0, 8.0) is True

    def test_at_or_above_baseline_floor_is_reliable(self):
        assert frequency_is_reliable(1, float(FREQ_MIN_BASELINE_TRAINS)) is True
        assert frequency_is_reliable(52, 42.0) is True


class TestNormalizerDelayFloor:
    """The re-aggregation path applies the delay floor to factor and level."""

    def _seg(self, avg_transit, baseline, **kw):
        delay = avg_transit - baseline
        return SegmentCongestion(
            from_station="NY",
            to_station="SE",  # adjacent NEC pair -> not expanded
            data_source="NJT",
            congestion_factor=avg_transit / baseline,
            congestion_level="severe",  # input ignored; recomputed
            avg_transit_minutes=avg_transit,
            baseline_minutes=baseline,
            sample_count=8,
            average_delay_minutes=delay,
            **kw,
        )

    def test_sub_minute_delay_suppressed_to_normal(self):
        """0.75 min actual over 0.75 min baseline (delay 0.75) -> normal/nominal,
        not severe, because the absolute delay is below the floor."""
        # avg 1.5 over baseline 0.75 => factor 2.0, delay 0.75 (< 1.0)
        result = normalize_aggregated_segments([self._seg(1.5, 0.75)])
        assert len(result) == 1
        seg = result[0]
        assert seg.congestion_factor == pytest.approx(1.0)
        assert seg.congestion_level == "normal"
        # Truthful delay is still reported for tooltips even though it's nominal.
        assert seg.average_delay_minutes == pytest.approx(0.75)

    def test_genuine_delay_still_escalates_on_short_hop(self):
        """3 min actual over 0.75 min baseline (delay 2.25) stays severe."""
        result = normalize_aggregated_segments([self._seg(3.0, 0.75)])
        assert len(result) == 1
        assert result[0].congestion_level == "severe"

    def test_cancellations_still_escalate_sub_minute_hop(self):
        """A short on-time hop with heavy cancellations must NOT be suppressed:
        the floor only touches the delay component; cancellations fold in after.
        """
        # On time (delay 0 -> clamped to 1.0) but 50% cancelled.
        seg = self._seg(0.75, 0.75, cancellation_count=8)
        # sample_count 8 running + 8 cancelled = 50% rate
        result = normalize_aggregated_segments([seg])
        assert len(result) == 1
        out = result[0]
        assert out.cancellation_rate == pytest.approx(50.0)
        assert out.congestion_factor == pytest.approx(1.0)
        # 1.0 + 50% * 0.015 = 1.75 -> severe
        assert out.congestion_level == "severe"


class TestNormalizerFrequencyFloor:
    """The re-aggregation path gates frequency levels on sample size."""

    def _seg(self, train_count, baseline_train_count):
        return SegmentCongestion(
            from_station="NY",
            to_station="SE",
            data_source="NJT",
            congestion_factor=1.0,
            congestion_level="normal",
            avg_transit_minutes=5.0,
            baseline_minutes=5.0,
            sample_count=train_count,
            average_delay_minutes=0.0,
            train_count=train_count,
            baseline_train_count=baseline_train_count,
            frequency_factor=(
                train_count / baseline_train_count if baseline_train_count else None
            ),
            frequency_level="reduced",  # input ignored; recomputed
        )

    def test_tiny_counts_get_no_frequency_level(self):
        """2 trains over a 2.5 baseline is noise -> frequency left unset (gray)."""
        result = normalize_aggregated_segments([self._seg(2, 2.5)])
        assert len(result) == 1
        seg = result[0]
        assert seg.frequency_factor is None
        assert seg.frequency_level is None
        # Raw counts are still reported for transparency/aggregation.
        assert seg.train_count == 2

    def test_robust_counts_get_a_frequency_level(self):
        """52 trains over a 42 baseline -> healthy, well above the floor."""
        result = normalize_aggregated_segments([self._seg(52, 42.0)])
        assert len(result) == 1
        seg = result[0]
        assert seg.frequency_factor == pytest.approx(52 / 42.0)
        assert seg.frequency_level == "healthy"

    def test_low_observed_against_solid_baseline_reports_severe(self):
        """Only 2 of 20 expected trains ran: a real severe service drop. The
        baseline is solid, so the level must be surfaced (severe), NOT hidden by
        an observed-count floor. Regression guard for the Codex P2 on #1598.
        """
        result = normalize_aggregated_segments([self._seg(2, 20.0)])
        assert len(result) == 1
        seg = result[0]
        assert seg.frequency_factor == pytest.approx(2 / 20.0)
        assert seg.frequency_level == "severe"

    def test_sparse_subsegments_aggregate_into_reliable_segment(self):
        """Two sparse raw NY->SE segments (each below the floor) sum to a
        trustworthy canonical segment and get a level. This is why the raw
        counts are reported even when individually unreliable."""
        raw = [self._seg(3, 2.5), self._seg(3, 2.5)]
        result = normalize_aggregated_segments(raw)
        assert len(result) == 1
        seg = result[0]
        # 6 trains over a 5.0 baseline -> reliable
        assert seg.train_count == 6
        assert seg.baseline_train_count == pytest.approx(5.0)
        assert seg.frequency_factor == pytest.approx(6 / 5.0)
        assert seg.frequency_level == "healthy"


async def _add_short_hop_journey(
    db: AsyncSession,
    train_id: str,
    scheduled_seconds: float,
    actual_seconds: float,
    *,
    departure: datetime,
    data_source: str = "SEPTA_METRO",
    from_station: str = "SEPM_A",
    to_station: str = "SEPM_B",
    is_cancelled: bool = False,
) -> None:
    """Create a two-stop journey whose scheduled and actual inter-stop times are
    specified in seconds — used to reproduce SEPTA Metro's sub-minute baselines.
    """
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        line_code="T1",
        line_name="Trolley",
        destination=to_station,
        origin_station_code=from_station,
        terminal_station_code=to_station,
        data_source=data_source,
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
            station_code=from_station,
            station_name=from_station,
            stop_sequence=1,
            scheduled_departure=departure,
            actual_departure=None if is_cancelled else departure,
        )
    )
    db.add(
        JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code=to_station,
            station_name=to_station,
            stop_sequence=2,
            scheduled_arrival=departure + timedelta(seconds=scheduled_seconds),
            actual_arrival=(
                None if is_cancelled else departure + timedelta(seconds=actual_seconds)
            ),
        )
    )
    await db.flush()


@pytest.mark.asyncio
class TestDelayFloorRealDB:
    """End-to-end: the optimized SQL path applies the delay floor."""

    async def test_sub_minute_noise_renders_normal(self, db_session: AsyncSession):
        """A trolley curb hop scheduled at 45s but taking 90s (factor 2.0, but
        only 45s of absolute delay) must render normal, not severe."""
        dep = now_et() - timedelta(minutes=20)
        for i in range(6):
            await _add_short_hop_journey(
                db_session,
                train_id=f"noise_{i}",
                scheduled_seconds=45,
                actual_seconds=90,  # 45s (0.75 min) delay -> below 1.0 floor
                departure=dep,
            )
        await db_session.commit()

        analyzer = CongestionAnalyzer()
        segments = await analyzer.get_network_congestion_optimized(
            db_session, time_window_hours=3, data_source="SEPTA_METRO"
        )
        seg = next(
            (
                s
                for s in segments
                if (s.from_station, s.to_station) == ("SEPM_A", "SEPM_B")
            ),
            None,
        )
        assert seg is not None, "short-hop segment should be present"
        assert seg.average_delay_minutes == pytest.approx(0.75, abs=0.05)
        assert seg.congestion_factor == pytest.approx(1.0)
        assert seg.congestion_level == "normal"

    async def test_genuine_delay_still_severe(self, db_session: AsyncSession):
        """A trolley hop scheduled at 45s but taking 4 min (>1 min absolute
        delay) is a real problem and stays escalated."""
        dep = now_et() - timedelta(minutes=20)
        for i in range(6):
            await _add_short_hop_journey(
                db_session,
                train_id=f"real_{i}",
                scheduled_seconds=45,
                actual_seconds=240,  # 3.25 min delay -> above floor
                departure=dep,
            )
        await db_session.commit()

        analyzer = CongestionAnalyzer()
        segments = await analyzer.get_network_congestion_optimized(
            db_session, time_window_hours=3, data_source="SEPTA_METRO"
        )
        seg = next(
            (
                s
                for s in segments
                if (s.from_station, s.to_station) == ("SEPM_A", "SEPM_B")
            ),
            None,
        )
        assert seg is not None
        assert seg.congestion_level == "severe"
