"""
Segment normalization service.

Expands journey segments to canonical consecutive station pairs
using route topology definitions. This ensures that skip-stop
segments (A→C) are properly attributed to all intermediate
canonical segments (A→B, B→C).
"""

from collections import defaultdict
from typing import Any

from structlog import get_logger

from trackrat.config.route_topology import (
    get_canonical_segments,
    get_routes_for_data_source,
)
from trackrat.services.congestion_types import (
    SegmentCongestion,
    effective_congestion_factor,
    frequency_is_reliable,
    get_congestion_level,
    get_frequency_level,
    reliable_congestion_factor,
)

logger = get_logger(__name__)

# Data sources where segments must match a known route topology.
# Unmatched segments (not found in any route) are dropped as anomalous —
# typically caused by sparse stop lists creating phantom long-distance
# connections (e.g., 96 St Q → Astoria-Ditmars Blvd N/W for subway).
# AMTRAK included because sparse API responses can create segments spanning
# hundreds of miles when intermediate stops lack actual times.
#
# SEPTA_METRO is deliberately EXCLUDED. Its route topology is built from
# direction_id=0 only, and each trolley curb stop has its own per-direction
# code (e.g. Baltimore Av & 42nd St is SEPM20876 outbound / SEPM20879
# inbound, but only SEPM20876 is in a route tuple). The collector persists
# the raw per-curb code, so every direction_id=1 trolley journey is keyed by
# codes absent from the topology and its (genuinely adjacent) segments would
# be flagged anomalous — ~174 false-positive warnings per collection cycle
# (issue #1573). These segments are between consecutive stops of a single
# journey, not phantom cross-branch jumps, so the route-match guard does more
# harm than good here. Metro is served schedule-first / frequency-first, so
# any residual segment noise carries no rider-facing cost.
_REQUIRE_ROUTE_MATCH_SOURCES: set[str] = {
    "NJT",
    "AMTRAK",
    "SUBWAY",
    "BART",
    "LIRR",
    "MNR",
    "MBTA",
    "METRA",
    "SEPTA_RR",
}


# Data sources whose route topology is NOT a physical single-direction path, so
# expanding a skip-stop segment through it fabricates non-physical sub-segments.
#
# SEPTA_METRO's topology is built from route_stops.txt direction_id=0 — a per-route
# UNION of every stop the route serves (subway-express + surface patterns) in a
# synthetic sort order that doubles back on itself. For the subway-surface trolleys
# (Routes 10/11/13/34/36) that order runs 40th St Portal -> surface Spruce St stops
# -> 40th-Market -> 37th-Spruce, but a real trolley runs 40th St Portal -> 37th-Spruce
# directly in the subway. Expanding that observed segment through the topology path
# explodes one clean hop into a zig-zag of fabricated sub-segments (e.g. the
# physically-impossible 40th-Market -> 37th-Spruce, an 837 m back-jump), which
# render as jagged congestion lines around University City. Metro's observed
# segments are already consecutive physical adjacencies, so we keep them as-is
# instead of expanding. Same topology unreliability that excludes SEPTA_METRO from
# route-match filtering above (issue #1573).
_SKIP_STOP_EXPANSION_EXCLUDED_SOURCES: set[str] = {"SEPTA_METRO"}


def _canonical_segments(
    data_source: str, from_station: str, to_station: str
) -> list[tuple[str, str]]:
    """Canonical consecutive pairs for a raw segment.

    Normally this expands a skip-stop segment (A->C) into its topology path
    (A->B, B->C). For sources in _SKIP_STOP_EXPANSION_EXCLUDED_SOURCES the
    topology is not a physical single-direction path, so expansion would
    fabricate zig-zag sub-segments; the observed segment is returned unchanged
    (it is already a physical adjacency).
    """
    if data_source in _SKIP_STOP_EXPANSION_EXCLUDED_SOURCES:
        return [(from_station, to_station)]
    return get_canonical_segments(
        data_source=data_source,
        from_station=from_station,
        to_station=to_station,
    )


def _is_segment_anomalous(from_station: str, to_station: str, data_source: str) -> bool:
    """Check if an unmatched segment is anomalous.

    For data sources in _REQUIRE_ROUTE_MATCH_SOURCES, checks whether both
    stations appear on the same route. Segments where no route contains both
    stations are anomalous — typically phantom cross-branch connections from
    sparse GTFS-RT data (e.g., 96 St Q → Astoria-Ditmars Blvd N/W).

    Segments that ARE on a route (even if already canonical) pass through.
    """
    if data_source not in _REQUIRE_ROUTE_MATCH_SOURCES:
        return False
    for route in get_routes_for_data_source(data_source):
        if route.contains_segment(from_station, to_station):
            return False
    return True


def _dominant_real_pair(
    data_list: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Return the real (from, to) leg that contributed the most samples.

    Each entry in ``data_list`` carries the real observed leg (``real_from`` /
    ``real_to``) it was expanded from plus that leg's ``sample_count``. The leg
    with the highest total sample count wins (ties broken deterministically by
    the pair itself). This gives clients a real, served station pair to navigate
    to when a canonical sub-segment's own endpoints are skip-stop stations no
    train stops at (e.g. Amtrak CWH→PHN, derived from the real TR→PH leg).
    """
    pair_samples: dict[tuple[str, str], int] = defaultdict(int)
    for d in data_list:
        pair_samples[(d["real_from"], d["real_to"])] += d["sample_count"]
    if not pair_samples:
        return None
    return max(pair_samples.items(), key=lambda kv: (kv[1], kv[0]))[0]


def normalize_aggregated_segments(
    raw_segments: list[SegmentCongestion],
) -> list[SegmentCongestion]:
    """
    Normalize aggregated segments by expanding non-canonical segments.

    When a segment spans multiple stations (A→C), this expands it to
    canonical pairs (A→B, B→C) and re-aggregates the statistics.

    Per the user's specification: A→C is counted BOTH towards A→B AND B→C
    (full attribution to each, not proportional splitting).

    Args:
        raw_segments: List of raw aggregated segment congestion data

    Returns:
        List of normalized and re-aggregated segment congestion data
    """
    # Accumulator for normalized segment data
    # Key: (from_station, to_station, data_source)
    # Value: list of (sample_count, total_minutes, baseline_minutes, delay_minutes,
    #                 cancellation_count, total_journeys)
    normalized_data: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(
        list
    )

    segments_expanded = 0
    segments_unchanged = 0

    for segment in raw_segments:
        # Get canonical segments for this segment
        canonical = _canonical_segments(
            segment.data_source, segment.from_station, segment.to_station
        )

        if len(canonical) == 1 and canonical[0] == (
            segment.from_station,
            segment.to_station,
        ):
            # Segment is already canonical or no route found — check route match
            if _is_segment_anomalous(
                segment.from_station, segment.to_station, segment.data_source
            ):
                logger.warning(
                    "anomalous_segment_filtered",
                    from_station=segment.from_station,
                    to_station=segment.to_station,
                    data_source=segment.data_source,
                )
                continue
            segments_unchanged += 1
        else:
            segments_expanded += 1

        # Attribute the full statistics to each canonical segment
        for from_station, to_station in canonical:
            key = (from_station, to_station, segment.data_source)
            normalized_data[key].append(
                {
                    "sample_count": segment.sample_count,
                    "avg_transit_minutes": segment.avg_transit_minutes,
                    "baseline_minutes": segment.baseline_minutes,
                    "average_delay_minutes": segment.average_delay_minutes,
                    "cancellation_count": segment.cancellation_count,
                    "cancellation_rate": segment.cancellation_rate,
                    # Frequency fields for Health mode
                    "train_count": segment.train_count,
                    "baseline_train_count": segment.baseline_train_count,
                    "frequency_factor": segment.frequency_factor,
                    "frequency_level": segment.frequency_level,
                    # The real observed leg this canonical pair came from — a pair
                    # of stations trains actually stopped at. Kept so clients can
                    # redirect a tap on a skip-stop canonical sub-segment to a
                    # real, served station board.
                    "real_from": segment.from_station,
                    "real_to": segment.to_station,
                }
            )

    # Re-aggregate normalized segments
    result = []
    for (from_station, to_station, data_source), data_list in normalized_data.items():
        # Combine statistics from all contributing segments
        total_samples = sum(d["sample_count"] for d in data_list)
        total_cancellations = sum(d["cancellation_count"] for d in data_list)
        dominant_real_pair = _dominant_real_pair(data_list)

        if total_samples == 0:
            # Only cancellation data - skip or create minimal entry
            if total_cancellations > 0:
                total_journeys = total_cancellations
                result.append(
                    SegmentCongestion(
                        from_station=from_station,
                        to_station=to_station,
                        data_source=data_source,
                        congestion_factor=1.0,
                        congestion_level="normal",
                        avg_transit_minutes=0.0,
                        baseline_minutes=0.0,
                        sample_count=0,
                        average_delay_minutes=0.0,
                        cancellation_count=total_cancellations,
                        cancellation_rate=(total_cancellations / total_journeys * 100),
                        dominant_real_pair=dominant_real_pair,
                    )
                )
            continue

        # Weighted average of transit times (weighted by sample count)
        weighted_transit = sum(
            d["avg_transit_minutes"] * d["sample_count"] for d in data_list
        )
        avg_transit = weighted_transit / total_samples

        # Weighted average of baseline times
        weighted_baseline = sum(
            d["baseline_minutes"] * d["sample_count"] for d in data_list
        )
        avg_baseline = weighted_baseline / total_samples

        # Calculate congestion factor
        congestion_factor = avg_transit / avg_baseline if avg_baseline > 0 else 1.0

        # Average delay
        average_delay = avg_transit - avg_baseline

        # Suppress sub-minute timing noise on closely-spaced stops before the
        # factor drives any color (see reliable_congestion_factor). Reassigned
        # so the reported factor and the level agree for both clients.
        congestion_factor = reliable_congestion_factor(congestion_factor, average_delay)

        # Cancellation rate
        total_journeys = total_samples + total_cancellations
        cancellation_rate = (
            (total_cancellations / total_journeys * 100) if total_journeys > 0 else 0.0
        )

        # Fold cancellations into the displayed level so a segment with many
        # cancelled trains is not shown as "normal" just because the trains
        # still running are on time. Mirrors the iOS client, which colors by
        # congestion_factor + cancellation_rate.
        congestion_level = get_congestion_level(
            effective_congestion_factor(congestion_factor, cancellation_rate)
        )

        # Aggregate frequency metrics (sum train_count and baseline_train_count)
        train_count: int | None = None
        baseline_train_count: float | None = None
        frequency_factor: float | None = None
        frequency_level: str | None = None

        # Sum up train counts from all contributing segments
        train_counts = [
            d["train_count"] for d in data_list if d["train_count"] is not None
        ]
        baseline_counts = [
            d["baseline_train_count"]
            for d in data_list
            if d["baseline_train_count"] is not None
        ]

        if train_counts:
            train_count = sum(train_counts)
        if baseline_counts:
            baseline_train_count = sum(baseline_counts)
        # Re-check reliability on the summed canonical segment: several sparse
        # raw sub-segments (each below the floor) can aggregate into a segment
        # with enough samples to trust. Only then assign a frequency level.
        if (
            train_count is not None
            and baseline_train_count is not None
            and frequency_is_reliable(train_count, baseline_train_count)
        ):
            frequency_factor = train_count / baseline_train_count
            frequency_level = get_frequency_level(frequency_factor)

        result.append(
            SegmentCongestion(
                from_station=from_station,
                to_station=to_station,
                data_source=data_source,
                congestion_factor=congestion_factor,
                congestion_level=congestion_level,
                avg_transit_minutes=avg_transit,
                baseline_minutes=avg_baseline,
                sample_count=total_samples,
                average_delay_minutes=average_delay,
                cancellation_count=total_cancellations,
                cancellation_rate=cancellation_rate,
                train_count=train_count,
                baseline_train_count=baseline_train_count,
                frequency_factor=frequency_factor,
                frequency_level=frequency_level,
                dominant_real_pair=dominant_real_pair,
            )
        )

    if segments_expanded > 0:
        logger.info(
            "segments_normalized",
            segments_expanded=segments_expanded,
            segments_unchanged=segments_unchanged,
            input_count=len(raw_segments),
            output_count=len(result),
        )

    # Filter out segments with no actual transit data (cancellation-only)
    # These have 0-minute transit times which are meaningless for visualization
    filtered_result = [s for s in result if s.sample_count > 0]
    if len(filtered_result) < len(result):
        logger.debug(
            "filtered_cancellation_only_segments",
            filtered_count=len(result) - len(filtered_result),
        )

    return filtered_result


def normalize_individual_segments(
    raw_segments: list[Any],
) -> list[Any]:
    """
    Normalize individual journey segments by expanding non-canonical segments.

    When a segment spans multiple stations (A→C), this expands it to
    canonical pairs (A→B, B→C). Each canonical segment inherits the
    full transit time and delay from the original segment.

    Args:
        raw_segments: List of IndividualJourneySegment objects

    Returns:
        List of normalized IndividualJourneySegment objects
    """
    from trackrat.config.stations import get_station_name
    from trackrat.models.api import IndividualJourneySegment

    result = []
    segments_expanded = 0

    for segment in raw_segments:
        # Get canonical segments for this segment
        canonical = _canonical_segments(
            segment.data_source, segment.from_station, segment.to_station
        )

        if len(canonical) == 1 and canonical[0] == (
            segment.from_station,
            segment.to_station,
        ):
            # Segment is already canonical or no route found — check route match
            if _is_segment_anomalous(
                segment.from_station, segment.to_station, segment.data_source
            ):
                logger.warning(
                    "anomalous_individual_segment_filtered",
                    from_station=segment.from_station,
                    to_station=segment.to_station,
                    data_source=segment.data_source,
                    journey_id=segment.journey_id,
                )
                continue
            result.append(segment)
            continue

        segments_expanded += 1

        # Create a new segment for each canonical pair
        # Each inherits the full timing data from the original
        for from_station, to_station in canonical:
            normalized = IndividualJourneySegment(
                journey_id=segment.journey_id,
                train_id=segment.train_id,
                from_station=from_station,
                to_station=to_station,
                from_station_name=get_station_name(from_station),
                to_station_name=get_station_name(to_station),
                data_source=segment.data_source,
                line=segment.line,
                scheduled_departure=segment.scheduled_departure,
                actual_departure=segment.actual_departure,
                scheduled_arrival=segment.scheduled_arrival,
                actual_arrival=segment.actual_arrival,
                scheduled_minutes=segment.scheduled_minutes,
                actual_minutes=segment.actual_minutes,
                delay_minutes=segment.delay_minutes,
                congestion_factor=segment.congestion_factor,
                congestion_level=segment.congestion_level,
                is_cancelled=segment.is_cancelled,
                journey_date=segment.journey_date,
            )
            result.append(normalized)

    if segments_expanded > 0:
        logger.info(
            "individual_segments_normalized",
            segments_expanded=segments_expanded,
            input_count=len(raw_segments),
            output_count=len(result),
        )

    return result
