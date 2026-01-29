"""
Unit tests for the segment normalizer service.
"""

from datetime import date, datetime

import pytest

from trackrat.models.api import IndividualJourneySegment
from trackrat.services.congestion_types import SegmentCongestion
from trackrat.services.segment_normalizer import (
    normalize_aggregated_segments,
    normalize_individual_segments,
)


class TestNormalizeAggregatedSegments:
    """Test the normalize_aggregated_segments function."""

    def test_adjacent_segment_unchanged(self):
        """Test that adjacent segments are not modified."""
        raw = [
            SegmentCongestion(
                from_station="NY",
                to_station="SE",
                data_source="NJT",
                congestion_factor=1.1,
                congestion_level="normal",
                avg_transit_minutes=5.0,
                baseline_minutes=4.5,
                sample_count=10,
                average_delay_minutes=0.5,
                cancellation_count=1,
                cancellation_rate=9.1,
            )
        ]
        result = normalize_aggregated_segments(raw)

        assert len(result) == 1
        assert result[0].from_station == "NY"
        assert result[0].to_station == "SE"
        assert result[0].sample_count == 10

    def test_skip_one_station_expands(self):
        """Test that a segment skipping one station expands to two segments."""
        # NY -> NP skips SE
        raw = [
            SegmentCongestion(
                from_station="NY",
                to_station="NP",
                data_source="NJT",
                congestion_factor=1.2,
                congestion_level="moderate",
                avg_transit_minutes=10.0,
                baseline_minutes=8.0,
                sample_count=5,
                average_delay_minutes=2.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        # Should expand to NY->SE and SE->NP
        assert len(result) == 2

        # Find segments by their from/to stations
        segments_by_key = {(s.from_station, s.to_station): s for s in result}

        assert ("NY", "SE") in segments_by_key
        assert ("SE", "NP") in segments_by_key

        # Each segment should have the full sample count (attributed to both)
        assert segments_by_key[("NY", "SE")].sample_count == 5
        assert segments_by_key[("SE", "NP")].sample_count == 5

    def test_multiple_segments_aggregation(self):
        """Test that overlapping normalized segments are properly aggregated."""
        # Two segments that will both expand to include NY->SE
        raw = [
            # NY -> NP expands to [NY->SE, SE->NP]
            SegmentCongestion(
                from_station="NY",
                to_station="NP",
                data_source="NJT",
                congestion_factor=1.2,
                congestion_level="moderate",
                avg_transit_minutes=10.0,
                baseline_minutes=8.0,
                sample_count=5,
                average_delay_minutes=2.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            ),
            # Direct NY -> SE segment
            SegmentCongestion(
                from_station="NY",
                to_station="SE",
                data_source="NJT",
                congestion_factor=1.1,
                congestion_level="normal",
                avg_transit_minutes=5.0,
                baseline_minutes=4.5,
                sample_count=10,
                average_delay_minutes=0.5,
                cancellation_count=1,
                cancellation_rate=9.1,
            ),
        ]
        result = normalize_aggregated_segments(raw)

        # Find the NY->SE segment
        ny_se = next(
            (s for s in result if s.from_station == "NY" and s.to_station == "SE"),
            None,
        )

        assert ny_se is not None
        # Should have combined sample counts: 5 + 10 = 15
        assert ny_se.sample_count == 15

    def test_unknown_segment_passthrough(self):
        """Test that unknown segments pass through unchanged."""
        raw = [
            SegmentCongestion(
                from_station="XX",
                to_station="YY",
                data_source="NJT",
                congestion_factor=1.0,
                congestion_level="normal",
                avg_transit_minutes=10.0,
                baseline_minutes=10.0,
                sample_count=5,
                average_delay_minutes=0.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        assert len(result) == 1
        assert result[0].from_station == "XX"
        assert result[0].to_station == "YY"

    def test_empty_input(self):
        """Test handling of empty input."""
        result = normalize_aggregated_segments([])
        assert result == []

    def test_path_segment_expansion(self):
        """Test expansion of PATH segments."""
        # PJS -> PNP skips PGR
        raw = [
            SegmentCongestion(
                from_station="PJS",
                to_station="PNP",
                data_source="PATH",
                congestion_factor=1.0,
                congestion_level="normal",
                avg_transit_minutes=4.0,
                baseline_minutes=4.0,
                sample_count=20,
                average_delay_minutes=0.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        # Should expand to PJS->PGR and PGR->PNP
        assert len(result) == 2
        segments_by_key = {(s.from_station, s.to_station): s for s in result}
        assert ("PJS", "PGR") in segments_by_key
        assert ("PGR", "PNP") in segments_by_key

    def test_cancellation_only_segment_filtered(self):
        """Test that segments with only cancellation data are filtered out.

        Cancellation-only segments have 0-minute transit times which are
        meaningless for congestion visualization, so they're excluded.
        """
        raw = [
            SegmentCongestion(
                from_station="NY",
                to_station="SE",
                data_source="NJT",
                congestion_factor=1.0,
                congestion_level="normal",
                avg_transit_minutes=0.0,
                baseline_minutes=0.0,
                sample_count=0,
                average_delay_minutes=0.0,
                cancellation_count=5,
                cancellation_rate=100.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        # Cancellation-only segments are filtered out
        assert len(result) == 0


class TestNormalizeIndividualSegments:
    """Test the normalize_individual_segments function."""

    def _create_segment(
        self,
        from_station: str,
        to_station: str,
        data_source: str = "NJT",
        journey_id: str = "123",
        train_id: str = "3835",
    ) -> IndividualJourneySegment:
        """Helper to create test segments."""
        base_time = datetime(2025, 7, 15, 8, 0, 0)
        return IndividualJourneySegment(
            journey_id=journey_id,
            train_id=train_id,
            from_station=from_station,
            to_station=to_station,
            from_station_name=f"Station {from_station}",
            to_station_name=f"Station {to_station}",
            data_source=data_source,
            scheduled_departure=base_time,
            actual_departure=base_time,
            scheduled_arrival=base_time,
            actual_arrival=base_time,
            scheduled_minutes=10.0,
            actual_minutes=12.0,
            delay_minutes=2.0,
            congestion_factor=1.2,
            congestion_level="moderate",
            is_cancelled=False,
            journey_date=date(2025, 7, 15),
        )

    def test_adjacent_segment_unchanged(self):
        """Test that adjacent segments are not modified."""
        raw = [self._create_segment("NY", "SE")]
        result = normalize_individual_segments(raw)

        assert len(result) == 1
        assert result[0].from_station == "NY"
        assert result[0].to_station == "SE"
        assert result[0].journey_id == "123"

    def test_skip_one_station_expands(self):
        """Test that a segment skipping one station expands."""
        # NY -> NP skips SE
        raw = [self._create_segment("NY", "NP")]
        result = normalize_individual_segments(raw)

        # Should expand to two segments
        assert len(result) == 2

        # Both segments should inherit the timing data
        for seg in result:
            assert seg.journey_id == "123"
            assert seg.train_id == "3835"
            assert seg.actual_minutes == 12.0
            assert seg.delay_minutes == 2.0

        # Check segment stations
        stations = [(s.from_station, s.to_station) for s in result]
        assert ("NY", "SE") in stations
        assert ("SE", "NP") in stations

    def test_skip_multiple_stations_expands(self):
        """Test that a segment skipping multiple stations expands."""
        # NY -> EZ skips SE, NP, NZ
        raw = [self._create_segment("NY", "EZ")]
        result = normalize_individual_segments(raw)

        # Should expand to four segments
        assert len(result) == 4

        stations = [(s.from_station, s.to_station) for s in result]
        assert ("NY", "SE") in stations
        assert ("SE", "NP") in stations
        assert ("NP", "NZ") in stations
        assert ("NZ", "EZ") in stations

    def test_multiple_journeys(self):
        """Test normalizing segments from multiple journeys."""
        raw = [
            self._create_segment("NY", "NP", journey_id="100", train_id="1001"),
            self._create_segment("SE", "NZ", journey_id="200", train_id="1002"),
        ]
        result = normalize_individual_segments(raw)

        # First expands to 2, second expands to 2
        assert len(result) == 4

        # Check journey IDs are preserved
        journey_100_segs = [s for s in result if s.journey_id == "100"]
        journey_200_segs = [s for s in result if s.journey_id == "200"]

        assert len(journey_100_segs) == 2
        assert len(journey_200_segs) == 2

    def test_unknown_segment_passthrough(self):
        """Test that unknown segments pass through unchanged."""
        raw = [self._create_segment("XX", "YY")]
        result = normalize_individual_segments(raw)

        assert len(result) == 1
        assert result[0].from_station == "XX"
        assert result[0].to_station == "YY"

    def test_empty_input(self):
        """Test handling of empty input."""
        result = normalize_individual_segments([])
        assert result == []

    def test_path_segment_expansion(self):
        """Test expansion of PATH segments."""
        # PJS -> PNP skips PGR
        raw = [self._create_segment("PJS", "PNP", data_source="PATH")]
        result = normalize_individual_segments(raw)

        assert len(result) == 2
        stations = [(s.from_station, s.to_station) for s in result]
        assert ("PJS", "PGR") in stations
        assert ("PGR", "PNP") in stations

    def test_station_names_updated(self):
        """Test that station names are updated for expanded segments."""
        raw = [self._create_segment("NY", "NP")]
        result = normalize_individual_segments(raw)

        # Station names should be looked up for the new segments
        for seg in result:
            # The get_station_name function should have been called
            # At minimum, the names should not be empty
            assert seg.from_station_name is not None
            assert seg.to_station_name is not None
