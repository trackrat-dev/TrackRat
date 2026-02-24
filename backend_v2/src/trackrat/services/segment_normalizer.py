"""
Segment normalization service.

Expands journey segments to canonical consecutive station pairs
using route topology definitions. This ensures that skip-stop
segments (A→C) are properly attributed to all intermediate
canonical segments (A→B, B→C).
"""

import math
from collections import defaultdict
from typing import Any

from structlog import get_logger

from trackrat.config.route_topology import get_canonical_segments
from trackrat.services.congestion_types import (
    SegmentCongestion,
    get_congestion_level,
    get_frequency_level,
)

logger = get_logger(__name__)

# Maximum distance (km) for segments with no matching route, by data source.
# Segments beyond this threshold are dropped as anomalous — typically caused
# by sparse GTFS-RT stop lists creating phantom cross-branch connections.
_MAX_UNMATCHED_SEGMENT_KM: dict[str, float] = {
    "SUBWAY": 10.0,
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _is_segment_anomalous(
    from_station: str, to_station: str, data_source: str
) -> bool:
    """Check if an unmatched segment spans an unreasonable geographic distance."""
    max_km = _MAX_UNMATCHED_SEGMENT_KM.get(data_source)
    if max_km is None:
        return False
    from trackrat.config.stations import get_station_coordinates

    from_coords = get_station_coordinates(from_station)
    to_coords = get_station_coordinates(to_station)
    if not from_coords or not to_coords:
        return False
    dist = _haversine_km(
        from_coords["lat"], from_coords["lon"],
        to_coords["lat"], to_coords["lon"],
    )
    return dist > max_km


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
        canonical = get_canonical_segments(
            data_source=segment.data_source,
            from_station=segment.from_station,
            to_station=segment.to_station,
        )

        if len(canonical) == 1 and canonical[0] == (
            segment.from_station,
            segment.to_station,
        ):
            # Segment is already canonical or no route found — check distance
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
                }
            )

    # Re-aggregate normalized segments
    result = []
    for (from_station, to_station, data_source), data_list in normalized_data.items():
        # Combine statistics from all contributing segments
        total_samples = sum(d["sample_count"] for d in data_list)
        total_cancellations = sum(d["cancellation_count"] for d in data_list)

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
        congestion_level = get_congestion_level(congestion_factor)

        # Average delay
        average_delay = avg_transit - avg_baseline

        # Cancellation rate
        total_journeys = total_samples + total_cancellations
        cancellation_rate = (
            (total_cancellations / total_journeys * 100) if total_journeys > 0 else 0.0
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
        freq_factors = [
            d["frequency_factor"]
            for d in data_list
            if d["frequency_factor"] is not None
        ]

        if train_counts:
            train_count = sum(train_counts)
        if baseline_counts:
            baseline_train_count = sum(baseline_counts)
            if train_count is not None and baseline_train_count > 0:
                frequency_factor = train_count / baseline_train_count
                frequency_level = get_frequency_level(frequency_factor)
        elif freq_factors:
            # No baseline available but source segments have frequency factors
            # (possible when merging segments with different data availability)
            frequency_factor = sum(freq_factors) / len(freq_factors)
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
        canonical = get_canonical_segments(
            data_source=segment.data_source,
            from_station=segment.from_station,
            to_station=segment.to_station,
        )

        if len(canonical) == 1 and canonical[0] == (
            segment.from_station,
            segment.to_station,
        ):
            # Segment is already canonical or no route found — check distance
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
