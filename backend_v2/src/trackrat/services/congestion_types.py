"""
Shared types for congestion analysis.

Separated from congestion.py to avoid circular imports with segment_normalizer.py.
"""

# Congestion level thresholds (factor = current_avg / baseline)
CONGESTION_THRESHOLD_NORMAL = 1.1  # <= 10% slower than baseline
CONGESTION_THRESHOLD_MODERATE = 1.25  # <= 25% slower than baseline
CONGESTION_THRESHOLD_HEAVY = 1.5  # <= 50% slower than baseline
# Above 1.5 = severe

# Frequency/health level thresholds (factor = train_count / baseline)
# Higher is better - measures service reliability
FREQ_THRESHOLD_HEALTHY = 0.9  # >= 90% of baseline trains
FREQ_THRESHOLD_MODERATE = 0.7  # >= 70% of baseline trains
FREQ_THRESHOLD_REDUCED = 0.5  # >= 50% of baseline trains
# Below 0.5 = severe

# Cancellation rate thresholds (percent of journeys cancelled in the window).
# The delay-based congestion factor only reflects trains that actually ran, so a
# line where many trains are cancelled but the survivors are on time would render
# green. These thresholds escalate the congestion level so heavy cancellations
# are visible on the map. See issue #1246.
CANCELLATION_THRESHOLD_MODERATE = 15.0  # >= 15% cancelled
CANCELLATION_THRESHOLD_HEAVY = 30.0  # >= 30% cancelled
CANCELLATION_THRESHOLD_SEVERE = 50.0  # >= 50% cancelled
# Minimum journeys (active + cancelled) with real-time data before the
# cancellation rate is trusted, to avoid small-sample noise flipping a
# low-traffic segment red on a single cancellation.
CANCELLATION_MIN_SAMPLE = 4

# Ordering of congestion levels from least to most severe, used to combine the
# delay-based and cancellation-based levels into a single displayed level.
_CONGESTION_SEVERITY = {"normal": 0, "moderate": 1, "heavy": 2, "severe": 3}

# Data sources where frequency/service health is more meaningful than delay stats.
# Mirrors iOS TrainSystem.preferredHighlightMode == .health
FREQUENCY_FIRST_SOURCES = {"SUBWAY", "PATH", "PATCO", "WMATA", "BART"}


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


def get_cancellation_level(cancellation_rate: float) -> str:
    """Determine a congestion level from a cancellation rate (percent)."""
    if cancellation_rate >= CANCELLATION_THRESHOLD_SEVERE:
        return "severe"
    elif cancellation_rate >= CANCELLATION_THRESHOLD_HEAVY:
        return "heavy"
    elif cancellation_rate >= CANCELLATION_THRESHOLD_MODERATE:
        return "moderate"
    else:
        return "normal"


def combine_congestion_levels(*levels: str) -> str:
    """Return the most severe of the given congestion levels."""
    return max(levels, key=lambda level: _CONGESTION_SEVERITY.get(level, 0))


def get_effective_congestion_level(
    congestion_factor: float,
    cancellation_rate: float,
    sample_count: int,
) -> str:
    """Congestion level combining transit-time delay and cancellations.

    The delay-based factor only reflects trains that ran, so a segment with
    many cancellations but on-time survivors would read as ``normal`` (green).
    When enough journeys are sampled, escalate to the more severe of the
    delay-based level and the cancellation-based level. See issue #1246.
    """
    level = get_congestion_level(congestion_factor)
    if sample_count >= CANCELLATION_MIN_SAMPLE:
        level = combine_congestion_levels(
            level, get_cancellation_level(cancellation_rate)
        )
    return level


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
