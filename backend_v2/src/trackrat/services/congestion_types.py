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

# Frequency/health level thresholds (factor = train_count / baseline)
# Higher is better - measures service reliability
FREQ_THRESHOLD_HEALTHY = 0.9  # >= 90% of baseline trains
FREQ_THRESHOLD_MODERATE = 0.7  # >= 70% of baseline trains
FREQ_THRESHOLD_REDUCED = 0.5  # >= 50% of baseline trains
# Below 0.5 = severe

# Minimum observed AND baseline train samples before a per-segment frequency
# level is trustworthy. The factor is a ratio of two counts; when both are
# tiny, ±1 train swings it across whole tiers. SEPTA Metro trolley stops carry
# a distinct per-direction/per-curb code, so each segment sees only a handful
# of trains (often 1-3) divided by an equally tiny baseline, producing
# healthy/moderate/reduced flip-flopping between adjacent stops. Validated
# subway-safe: every SUBWAY segment has a baseline >= 6 and all but one have
# >= 5 observed trains, so real subway frequency signal is unaffected.
FREQ_MIN_SAMPLE_TRAINS = 5

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
    congestion_factor: float, cancellation_rate: float = 0.0
) -> float:
    """Fold a segment's cancellation rate into its congestion factor.

    ``cancellation_rate`` is a percentage (0-100). Heavy cancellations raise the
    effective factor so a segment with many cancelled trains is not reported as
    "normal" just because the few trains still running happen to be on time.
    """
    return (
        congestion_factor + max(0.0, cancellation_rate) * CANCELLATION_CONGESTION_WEIGHT
    )


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
    """Whether a segment has enough samples for a trustworthy frequency level.

    Both the observed count and the historical baseline must reach
    ``FREQ_MIN_SAMPLE_TRAINS``; otherwise the ratio is dominated by noise and
    should be left unset (clients render no frequency color and fall back).
    """
    return (
        train_count is not None
        and baseline_train_count is not None
        and train_count >= FREQ_MIN_SAMPLE_TRAINS
        and baseline_train_count >= FREQ_MIN_SAMPLE_TRAINS
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
