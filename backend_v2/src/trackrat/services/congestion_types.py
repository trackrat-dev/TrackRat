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


def congestion_level_with_cancellations(
    congestion_factor: float, cancellation_rate: float, total_journeys: int
) -> tuple[str, bool]:
    """Congestion tier including cancellations, and whether they drove it.

    Returns ``(level, cancellation_driven)`` where ``level`` is the tier of the
    cancellation-blended factor, and ``cancellation_driven`` is True when that
    blend escalated the segment above the tier its delays alone would produce.

    Clients need the flag to label the segment truthfully. Without it a segment
    escalated purely by cancellations renders as "Severe delays" next to an
    average delay of zero and an "On time" caption — the contradiction reported
    in issue #1638. The blended tier is still the right thing to *color* by:
    cancellations are a real service problem, they are just not delays.
    """
    delay_level = get_congestion_level(congestion_factor)
    blended_level = get_congestion_level(
        effective_congestion_factor(
            congestion_factor, cancellation_rate, total_journeys
        )
    )
    return blended_level, blended_level != delay_level


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
        cancellation_driven: bool = False,
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
        # True when cancellations, not delays, pushed this segment above the
        # tier its running trains earned — see congestion_level_with_cancellations.
        self.cancellation_driven = cancellation_driven
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
