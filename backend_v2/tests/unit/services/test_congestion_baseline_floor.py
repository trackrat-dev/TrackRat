"""Baseline floor for the congestion factor (issue #1715).

The congestion factor is a ratio, so before the floor the same lost minutes
coloured a short hop far redder than a long one. That made the intermediate
tiers unreachable on most of the network and produced the reported
"green directly to red directly back to green" map: on production NJT only 4 of
272 segments were moderate, and of the 60 adjacent segment pairs whose colours
differed, 48 differed by two or three tiers at once.

These tests pin the property that fixes it — the colour tracks minutes lost,
not how short the hop is — and the two boundaries that must survive it: long
hops keep their true ratio, and the sub-minute noise floor still wins.
"""

import pytest

from trackrat.services.congestion_types import (
    CONGESTION_BASELINE_FLOOR_MINUTES,
    congestion_factor_from_delay,
    get_congestion_level,
)


class TestBaselineFloorRemovesShortHopAmplification:
    def test_same_delay_reads_the_same_on_every_short_hop(self):
        """Two minutes lost is two minutes lost, whether the hop is 2 or 9 min.

        This is the whole point of the floor. Before it, 2 minutes on a 3-minute
        hop was 1.67 (severe) while the same 2 minutes on a 9-minute hop was
        1.22 (moderate) — adjacent segments of one line, two tiers apart, from
        identical delays.
        """
        factors = [
            congestion_factor_from_delay(2.0, baseline)
            for baseline in (2.0, 3.0, 5.0, 9.0, CONGESTION_BASELINE_FLOOR_MINUTES)
        ]
        assert factors == [pytest.approx(1.2)] * len(factors)
        assert {get_congestion_level(f) for f in factors} == {"moderate"}

    def test_short_hop_no_longer_leaps_past_moderate(self):
        """On a 3-minute hop the smallest reportable delay used to land on heavy.

        MIN_CONGESTION_DELAY_MINUTES pins anything under a minute to exactly 1.0,
        so 1 minute is the first delay a segment can show. The raw ratio made
        that 1 + 1/3 = 1.33 — heavy — meaning a segment stepped straight from
        green to the third tier. Under the floor it is 1.10, the top of normal,
        and escalation from there is gradual.
        """
        assert congestion_factor_from_delay(1.0, 3.0) == pytest.approx(1.1)
        assert get_congestion_level(congestion_factor_from_delay(1.0, 3.0)) == "normal"
        assert (
            get_congestion_level(congestion_factor_from_delay(1.5, 3.0)) == "moderate"
        )
        assert get_congestion_level(congestion_factor_from_delay(3.0, 3.0)) == "heavy"
        assert get_congestion_level(congestion_factor_from_delay(6.0, 3.0)) == "severe"

    def test_tier_boundaries_land_on_whole_lost_minutes(self):
        """At the floor the thresholds mean 1, 2.5 and 5 minutes lost.

        The first boundary coinciding with MIN_CONGESTION_DELAY_MINUTES is what
        closes the dead band: the smallest delay the map is willing to report is
        exactly the delay at which colour starts to move.
        """
        floor = CONGESTION_BASELINE_FLOOR_MINUTES
        assert (
            get_congestion_level(congestion_factor_from_delay(1.0, floor)) == "normal"
        )
        assert (
            get_congestion_level(congestion_factor_from_delay(1.01, floor))
            == "moderate"
        )
        assert (
            get_congestion_level(congestion_factor_from_delay(2.51, floor)) == "heavy"
        )
        assert (
            get_congestion_level(congestion_factor_from_delay(5.01, floor)) == "severe"
        )


class TestBaselineFloorLeavesLongHopsAlone:
    def test_above_the_floor_the_factor_is_the_untouched_ratio(self):
        """A 20-minute leg is measured against its own 20 minutes, as before.

        The floor exists to stop a tiny denominator exaggerating; a large one
        needs no correction, and clamping it would understate real delays on
        long legs.
        """
        for baseline in (10.0, 12.5, 20.0, 45.0):
            for delay in (-3.0, 0.0, 2.0, 11.0):
                assert congestion_factor_from_delay(delay, baseline) == pytest.approx(
                    (baseline + delay) / baseline
                )

    def test_long_hop_severe_delay_still_severe(self):
        """11 minutes lost on a 20-minute leg stays severe (1.55)."""
        factor = congestion_factor_from_delay(11.0, 20.0)
        assert factor == pytest.approx(1.55)
        assert get_congestion_level(factor) == "severe"


class TestBaselineFloorEdgeCases:
    def test_early_running_segment_reports_below_one(self):
        """A segment running early keeps a factor under 1.0, as the ratio did."""
        assert congestion_factor_from_delay(-2.0, 4.0) == pytest.approx(0.8)
        assert get_congestion_level(congestion_factor_from_delay(-2.0, 4.0)) == "normal"

    def test_no_delay_is_exactly_nominal(self):
        for baseline in (0.5, 5.0, 30.0):
            assert congestion_factor_from_delay(0.0, baseline) == 1.0

    @pytest.mark.parametrize("baseline", [0.0, -1.0])
    def test_missing_baseline_reports_nominal(self, baseline):
        """No scheduled time and no usable actuals means no scale to measure
        against, so the segment must report nominal rather than divide by zero."""
        assert congestion_factor_from_delay(5.0, baseline) == 1.0

    def test_matches_the_plain_ratio_it_replaced_at_the_floor(self):
        """Exactly at the floor the two formulations agree, so the change is
        continuous — no jump in colour as a baseline crosses 10 minutes."""
        floor = CONGESTION_BASELINE_FLOOR_MINUTES
        just_below = congestion_factor_from_delay(3.0, floor - 0.001)
        just_above = congestion_factor_from_delay(3.0, floor + 0.001)
        assert just_below == pytest.approx(just_above, abs=1e-3)
