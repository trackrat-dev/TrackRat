"""
Shared types for congestion analysis.

Separated from congestion.py to avoid circular imports with segment_normalizer.py.
"""

# Congestion level thresholds (factor = current_avg / baseline)
CONGESTION_THRESHOLD_NORMAL = 1.1  # <= 10% slower than baseline
CONGESTION_THRESHOLD_MODERATE = 1.25  # <= 25% slower than baseline
CONGESTION_THRESHOLD_HEAVY = 1.5  # <= 50% slower than baseline
# Above 1.5 = severe

# Minimum absolute delay (minutes) before a segment counts as congested.
# The congestion factor is a ratio against the scheduled inter-station time,
# so on closely-spaced stops with sub-minute baselines (SEPTA Metro trolley
# curb stops sit ~30-60s apart) the minute-resolution rounding of GTFS-RT
# feeds pushes the ratio to 1.5-2.0 — heavy/severe — from a few seconds of
# noise. Requiring a real ~1 minute of lost time before escalating suppresses
# that jitter while leaving genuine delays untouched: rail segments with real
# problems lose multiple minutes (validated against NJT: 14/15 heavy-severe
# segments keep their level), and a truly stuck train on a short hop still
# loses >= 1 min and stays escalated.
MIN_CONGESTION_DELAY_MINUTES = 1.0

# Minimum baseline (minutes) used as the denominator when converting a segment's
# lost time into a congestion factor. The factor is a ratio, so identical
# absolute delay reads wildly differently depending on how short the hop is: two
# minutes lost on a 3-minute baseline is 1.67 (severe) while the same two
# minutes on a 20-minute baseline is 1.10 (normal). Most inter-station hops are
# short — on production NJT the median segment baseline is 5 minutes and the
# 10th percentile is 3 — so across most of the network the factor is dominated
# by the shortness of the hop rather than by the delay.
#
# That compression is what produced issue #1715's "green directly to red
# directly back to green". With MIN_CONGESTION_DELAY_MINUTES suppressing
# everything under a minute, the smallest delay a segment can show is 1 minute,
# which on a 3-minute hop is already 1.33 — heavy. The moderate tier is
# therefore unreachable in practice and adjacent segments leap two or three
# tiers at once: measured on production NJT, of the 60 adjacent segment pairs
# whose colours differed, 48 differed by >= 2 tiers, and only 4 of 272 segments
# were moderate.
#
# Flooring the denominator makes the factor track lost minutes on short hops
# while leaving long hops on their true ratio (the max() is a no-op above the
# floor, so a 20-minute leg is unaffected). At the floor the tier boundaries
# land on 1, 2.5 and 5 minutes lost, so the first escalation lines up exactly
# with MIN_CONGESTION_DELAY_MINUTES instead of vaulting past it. Re-simulated
# against the same production data, 3-tier jumps between adjacent segments fall
# from 26 to 8.
CONGESTION_BASELINE_FLOOR_MINUTES = 10.0

# Weight applied to a segment's cancellation rate (a percentage, 0-100) when
# folding cancellations into the congestion factor. Mirrors the iOS client's
# CongestionColors.cancellationCongestionWeight (ios/.../Utilities/Extensions.swift)
# so the web map (which colors by congestion_level) and iOS (which colors by
# congestion_factor + cancellation_rate) stay consistent: ~1 congestion tier per
# 10% of scheduled trains cancelled.
CANCELLATION_CONGESTION_WEIGHT = 0.015

# Minimum number of scheduled journeys on a segment (running + cancelled) before
# cancellations may escalate its congestion tier. The rate is
# cancelled / (running + cancelled), so on a sparse off-peak segment a single
# cancellation against a single running train is 50% — on its own enough to
# paint the segment severe (1.0 + 50 * 0.015 = 1.75) while the trains that ran
# were exactly on time. That is issue #1638: red with no delays, on an NJCL
# stretch running 1-2 trains/hour.
#
# The floor is the cancellation analogue of FREQ_MIN_BASELINE_TRAINS and is set
# to the same value: below it the rate quantizes so coarsely (0%, 50%, 100% at
# two journeys) that it cannot distinguish a service problem from one cancelled
# train. The delay component is deliberately NOT gated — a real delay is real
# however few trains measured it — so a genuinely slow sparse segment still
# escalates on its own merits.
CANCELLATION_MIN_JOURNEYS = 5

# What produced a segment's congestion level — see congestion_level_and_cause.
# Clients pick the noun for the caption from this ("Heavy delays" vs "Heavy
# cancellations" vs "Heavy delays and cancellations"), so it must distinguish a
# purely-cancellation escalation from one layered on top of real delays.
CONGESTION_CAUSE_DELAYS = "delays"
CONGESTION_CAUSE_CANCELLATIONS = "cancellations"
CONGESTION_CAUSE_BOTH = "both"

# Frequency/health level thresholds (factor = train_count / baseline)
# Higher is better - measures service reliability
FREQ_THRESHOLD_HEALTHY = 0.9  # >= 90% of baseline trains
FREQ_THRESHOLD_MODERATE = 0.7  # >= 70% of baseline trains
FREQ_THRESHOLD_REDUCED = 0.5  # >= 50% of baseline trains
# Below 0.5 = severe

# Minimum historical baseline train count before a per-segment frequency level
# is trustworthy. The factor is observed / baseline; when the *baseline* (the
# denominator) is tiny, ±1 train swings the ratio across whole tiers. SEPTA
# Metro trolley stops carry a distinct per-direction/per-curb code, so each
# segment's baseline is only a handful of trains, producing
# healthy/moderate/reduced flip-flopping between adjacent stops.
#
# The guard is on the baseline ONLY, not the observed count: a low observed
# count against a solid baseline (e.g. 2 of 20 expected trains ran -> 0.1) is a
# genuine severe/reduced service drop that health mode exists to surface, and
# must not be discarded as "too few samples". Validated subway-safe: every
# SUBWAY segment has a baseline >= 6, so real subway frequency signal is
# unaffected.
FREQ_MIN_BASELINE_TRAINS = 5

# Data sources where frequency/service health is more meaningful than delay stats.
# Mirrors iOS TrainSystem.preferredHighlightMode == .health
FREQUENCY_FIRST_SOURCES = {"SUBWAY", "PATH", "PATCO", "WMATA", "BART", "SEPTA_METRO"}


def congestion_factor_from_delay(
    average_delay_minutes: float, baseline_minutes: float
) -> float:
    """Congestion factor for a segment that lost ``average_delay_minutes``.

    Algebraically ``current_average / baseline``, but written as
    ``1 + delay / baseline`` so the denominator can be floored at
    ``CONGESTION_BASELINE_FLOOR_MINUTES`` — see that constant for why the raw
    ratio makes short hops swing across whole tiers on a delay a long hop would
    call normal. Above the floor this is exactly the old ratio.

    A non-positive baseline (no scheduled time and no usable actuals) has no
    scale to measure against, so the segment reports nominal.
    """
    if baseline_minutes <= 0:
        return 1.0
    return 1.0 + average_delay_minutes / max(
        baseline_minutes, CONGESTION_BASELINE_FLOOR_MINUTES
    )


def get_congestion_level(congestion_factor: float) -> str:
    """Determine congestion level from a congestion factor."""
    if congestion_factor <= CONGESTION_THRESHOLD_NORMAL:
        return "normal"
    elif congestion_factor <= CONGESTION_THRESHOLD_MODERATE:
        return "moderate"
    elif congestion_factor <= CONGESTION_THRESHOLD_HEAVY:
        return "heavy"
    else:
        return "severe"


def effective_congestion_factor(
    congestion_factor: float,
    cancellation_rate: float = 0.0,
    total_journeys: int | None = None,
) -> float:
    """Fold a segment's cancellation rate into its congestion factor.

    ``cancellation_rate`` is a percentage (0-100). Heavy cancellations raise the
    effective factor so a segment with many cancelled trains is not reported as
    "normal" just because the few trains still running happen to be on time.

    ``total_journeys`` is the number of journeys that rate was computed from
    (running + cancelled). When supplied and below ``CANCELLATION_MIN_JOURNEYS``
    the cancellation term is dropped entirely: the rate is too coarse on a
    sparse segment to be evidence of anything (issue #1638). Pass it wherever
    the count is known; it defaults to ``None`` so the pure delay/cancellation
    arithmetic can still be exercised on its own.
    """
    if total_journeys is not None and total_journeys < CANCELLATION_MIN_JOURNEYS:
        return congestion_factor
    return (
        congestion_factor + max(0.0, cancellation_rate) * CANCELLATION_CONGESTION_WEIGHT
    )


def congestion_level_and_cause(
    congestion_factor: float,
    cancellation_rate: float,
    total_journeys: int,
    average_delay_minutes: float,
) -> tuple[str, str]:
    """Congestion tier including cancellations, and what actually produced it.

    Returns ``(level, cause)`` where ``level`` is the tier of the
    cancellation-blended factor and ``cause`` is one of:

    - ``"delays"`` — cancellations did not move the tier. The segment's colour
      is entirely the running trains' lost time (or it is normal).
    - ``"cancellations"`` — cancellations moved the tier and the delays alone
      were normal, so the trains that ran were fine.
    - ``"both"`` — the segment was already escalated on delays *and*
      cancellations pushed it further.

    Clients need this to label the segment truthfully. Without it a segment
    escalated purely by cancellations renders as "Severe delays" next to an
    average delay of zero and an "On time" caption — the contradiction reported
    in issue #1638. A plain "were cancellations involved?" boolean is not
    enough: it cannot distinguish that case from a genuinely delayed segment
    that cancellations pushed up one further tier, and clients reading such a
    flag as "no delays" would then contradict a real, non-zero delay.

    The tier alone cannot decide whether a delay exists. ``congestion_factor``
    is a ratio against the segment's baseline, so on a long leg a real delay can
    sit inside the normal tier: 42 minutes against a 40-minute baseline is a
    factor of 1.05 — "normal" — while ``average_delay_minutes`` is 2.0, well
    above ``MIN_CONGESTION_DELAY_MINUTES``. Reporting that as ``"cancellations"``
    would reproduce the very contradiction this function exists to prevent: the
    web drops the segment from its delayed count and iOS labels it
    "Heavy cancellations", both directly beside a rendered "+2m".

    So the delay is judged by the same floor the map itself uses.
    ``average_delay_minutes`` below that floor is jitter the map declines to
    show, and the segment truthfully reports ``"cancellations"``; at or above
    it the delay is real and the cause is ``"both"`` however small the tier
    movement was.

    The comparison is signed, not absolute. A segment running *early* clears an
    absolute floor but has no delay to name, and both clients render a delay
    only when it is positive — so calling it ``"both"`` would put it in the web's
    delayed count with no "+Nm" beside it, the same class of contradiction one
    tier down.
    """
    delay_level = get_congestion_level(congestion_factor)
    blended_level = get_congestion_level(
        effective_congestion_factor(
            congestion_factor, cancellation_rate, total_journeys
        )
    )
    if blended_level == delay_level:
        return blended_level, CONGESTION_CAUSE_DELAYS
    # Either evidence of a real delay is enough. The tier check is not redundant
    # for callers that pass a factor which has not been through
    # reliable_congestion_factor: for those, an escalated tier is the only
    # delay signal available.
    delay_is_reportable = (
        average_delay_minutes >= MIN_CONGESTION_DELAY_MINUTES or delay_level != "normal"
    )
    if not delay_is_reportable:
        return blended_level, CONGESTION_CAUSE_CANCELLATIONS
    return blended_level, CONGESTION_CAUSE_BOTH


def reliable_congestion_factor(
    congestion_factor: float, average_delay_minutes: float
) -> float:
    """Suppress sub-minute timing noise from the congestion factor.

    Returns a nominal factor (1.0) when trains lose less than
    ``MIN_CONGESTION_DELAY_MINUTES`` of absolute time on the segment, so the
    minute-resolution jitter of GTFS-RT feeds on closely-spaced stops does not
    read as congestion. Genuine delays (>= the floor) keep their real factor.

    Applied to the delay component only — cancellations are folded in
    separately via ``effective_congestion_factor``, so a heavily-cancelled but
    on-time segment still escalates.
    """
    if abs(average_delay_minutes) < MIN_CONGESTION_DELAY_MINUTES:
        return 1.0
    return congestion_factor


def get_frequency_level(frequency_factor: float) -> str:
    """Determine frequency/health level from a frequency factor.

    Higher is better: 1.0 means running at baseline, <1.0 means fewer trains.
    """
    if frequency_factor >= FREQ_THRESHOLD_HEALTHY:
        return "healthy"
    elif frequency_factor >= FREQ_THRESHOLD_MODERATE:
        return "moderate"
    elif frequency_factor >= FREQ_THRESHOLD_REDUCED:
        return "reduced"
    else:
        return "severe"


def frequency_is_reliable(
    train_count: int | None, baseline_train_count: float | None
) -> bool:
    """Whether a segment has a trustworthy frequency baseline.

    The historical baseline (the denominator) must reach
    ``FREQ_MIN_BASELINE_TRAINS``; below that the observed/baseline ratio is
    dominated by noise and no frequency level should be shown. The observed
    count is deliberately NOT floored — a low observed count against a solid
    baseline is a real service reduction health mode should surface (2/20 = 0.1
    is severe, not noise). ``train_count`` only needs to be present so the ratio
    can be computed.
    """
    return (
        train_count is not None
        and baseline_train_count is not None
        and baseline_train_count >= FREQ_MIN_BASELINE_TRAINS
    )


class SegmentCongestion:
    """Congestion data for a route segment."""

    def __init__(
        self,
        from_station: str,
        to_station: str,
        data_source: str,
        congestion_factor: float,
        congestion_level: str,
        avg_transit_minutes: float,
        baseline_minutes: float,
        sample_count: int,
        average_delay_minutes: float,
        cancellation_count: int = 0,
        cancellation_rate: float = 0.0,
        congestion_cause: str = CONGESTION_CAUSE_DELAYS,
        # Frequency/health metrics
        train_count: int | None = None,
        baseline_train_count: float | None = None,
        frequency_factor: float | None = None,
        frequency_level: str | None = None,
        # Real observed leg this (possibly canonical) segment was derived from
        dominant_real_pair: tuple[str, str] | None = None,
    ):
        self.from_station = from_station
        self.to_station = to_station
        self.data_source = data_source
        self.congestion_factor = congestion_factor
        self.congestion_level = congestion_level
        self.avg_transit_minutes = avg_transit_minutes
        self.baseline_minutes = baseline_minutes
        self.sample_count = sample_count
        self.average_delay_minutes = average_delay_minutes
        self.cancellation_count = cancellation_count
        self.cancellation_rate = cancellation_rate
        # What produced congestion_level: "delays", "cancellations", or "both"
        # — see congestion_level_and_cause.
        self.congestion_cause = congestion_cause
        # Frequency/health metrics (None for schedule-only sources)
        self.train_count = train_count
        self.baseline_train_count = baseline_train_count
        self.frequency_factor = frequency_factor
        self.frequency_level = frequency_level
        # The real (from, to) leg — a pair of stations trains actually stopped
        # at — that contributed the most samples to this canonical segment.
        # Skip-stop expansion produces canonical sub-segments whose endpoints no
        # train stops at (e.g. Amtrak TR→PH -> CWH→PHN); clients use this to
        # redirect a tap on such a segment to a real, served station board.
        self.dominant_real_pair = dominant_real_pair

    @property
    def transit_time_multiplier(self) -> float:
        """How much slower than baseline this segment physically ran.

        The literal ``avg_transit / baseline`` ratio, with the same sub-minute
        noise floor ``congestion_factor`` gets. Deliberately NOT floored by
        ``CONGESTION_BASELINE_FLOOR_MINUTES``: that floor exists so *colour*
        tracks minutes lost rather than hop length (#1715), which is the right
        scale for a map and the wrong one for arithmetic. A 2-minute hop taking
        4 minutes really is 2x slower, and a forecaster multiplying expected
        delay by 1.2 instead of 2.0 would quietly under-predict exactly the
        short segments where trains bunch.

        Kept separate rather than reusing ``congestion_factor`` so the display
        scale can be retuned without silently moving forecasts.
        """
        if self.baseline_minutes <= 0:
            return 1.0
        return reliable_congestion_factor(
            self.avg_transit_minutes / self.baseline_minutes,
            self.average_delay_minutes,
        )

    @property
    def effective_congestion_factor(self) -> float:
        """The factor ``congestion_level`` was bucketed from.

        ``congestion_factor`` with this segment's cancellation rate folded in,
        so clients can shade the map continuously between the tier colours
        without re-deriving the cancellation weighting themselves (issue #1715).
        Delegates to the module-level function of the same name — the single
        source of the weighting and its sparse-segment gate.
        """
        return effective_congestion_factor(
            self.congestion_factor,
            self.cancellation_rate,
            self.sample_count + self.cancellation_count,
        )
