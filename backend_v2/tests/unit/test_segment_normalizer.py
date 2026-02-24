"""
Unit tests for the segment normalizer service.
"""

from datetime import date, datetime

import pytest

from trackrat.models.api import IndividualJourneySegment
from trackrat.services.congestion_types import SegmentCongestion
from trackrat.services.segment_normalizer import (
    _haversine_km,
    _is_segment_anomalous,
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

    def test_lirr_segment_expansion(self):
        """Test expansion of LIRR segments (Babylon Branch, trunk included)."""
        # NY -> JAM on Babylon Branch skips WDD, FHL, KGN
        raw = [
            SegmentCongestion(
                from_station="NY",
                to_station="JAM",
                data_source="LIRR",
                congestion_factor=1.1,
                congestion_level="normal",
                avg_transit_minutes=15.0,
                baseline_minutes=14.0,
                sample_count=8,
                average_delay_minutes=1.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        assert len(result) == 4
        segments_by_key = {(s.from_station, s.to_station): s for s in result}
        assert ("NY", "WDD") in segments_by_key
        assert ("WDD", "FHL") in segments_by_key
        assert ("FHL", "KGN") in segments_by_key
        assert ("KGN", "JAM") in segments_by_key

    def test_mnr_segment_expansion(self):
        """Test expansion of MNR segments (Hudson Line)."""
        # GCT -> MEYS on Hudson Line skips M125
        raw = [
            SegmentCongestion(
                from_station="GCT",
                to_station="MEYS",
                data_source="MNR",
                congestion_factor=1.0,
                congestion_level="normal",
                avg_transit_minutes=8.0,
                baseline_minutes=8.0,
                sample_count=12,
                average_delay_minutes=0.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)

        assert len(result) == 2
        segments_by_key = {(s.from_station, s.to_station): s for s in result}
        assert ("GCT", "M125") in segments_by_key
        assert ("M125", "MEYS") in segments_by_key

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
        # NY -> EZ skips SE, NP, NA, NZ
        raw = [self._create_segment("NY", "EZ")]
        result = normalize_individual_segments(raw)

        # Should expand to five segments (NA now between NP and NZ)
        assert len(result) == 5

        stations = [(s.from_station, s.to_station) for s in result]
        assert ("NY", "SE") in stations
        assert ("SE", "NP") in stations
        assert ("NP", "NA") in stations
        assert ("NA", "NZ") in stations
        assert ("NZ", "EZ") in stations

    def test_multiple_journeys(self):
        """Test normalizing segments from multiple journeys."""
        raw = [
            self._create_segment("NY", "NP", journey_id="100", train_id="1001"),
            self._create_segment("SE", "NZ", journey_id="200", train_id="1002"),
        ]
        result = normalize_individual_segments(raw)

        # First expands to 2 (NY->SE, SE->NP), second expands to 3 (SE->NP, NP->NA, NA->NZ)
        assert len(result) == 5

        # Check journey IDs are preserved
        journey_100_segs = [s for s in result if s.journey_id == "100"]
        journey_200_segs = [s for s in result if s.journey_id == "200"]

        assert len(journey_100_segs) == 2
        assert len(journey_200_segs) == 3

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

    def test_lirr_individual_segment_expansion(self):
        """Test LIRR individual segment expansion."""
        # JAM -> LYN on Babylon Branch skips VSM
        raw = [self._create_segment("JAM", "LYN", data_source="LIRR")]
        result = normalize_individual_segments(raw)

        assert len(result) == 2
        stations = [(s.from_station, s.to_station) for s in result]
        assert ("JAM", "VSM") in stations
        assert ("VSM", "LYN") in stations

    def test_mnr_individual_segment_expansion(self):
        """Test MNR individual segment expansion."""
        # MSTM -> MTMH on New Canaan Branch skips MGLB and MSPD
        raw = [self._create_segment("MSTM", "MTMH", data_source="MNR")]
        result = normalize_individual_segments(raw)

        assert len(result) == 3
        stations = [(s.from_station, s.to_station) for s in result]
        assert ("MSTM", "MGLB") in stations
        assert ("MGLB", "MSPD") in stations
        assert ("MSPD", "MTMH") in stations

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


class TestHaversineKm:
    """Test the haversine distance helper function."""

    def test_same_point_returns_zero(self):
        """Test that distance between same point is zero."""
        assert _haversine_km(40.75, -73.99, 40.75, -73.99) == 0.0

    def test_known_distance_nyc_subway(self):
        """Test haversine against known NYC subway station distances.

        Penn Station (SA28) to Times Square (SA30) is approximately 0.7 km.
        """
        # SA28 (34 St-Penn Station): 40.752287, -73.993391
        # SA30 (59 St-Columbus Circle): 40.768247, -73.981929
        dist = _haversine_km(40.752287, -73.993391, 40.768247, -73.981929)
        assert 1.0 < dist < 3.0, f"Penn Station to Columbus Circle should be ~2 km, got {dist:.2f}"

    def test_cross_branch_distance_large(self):
        """Test that distance between SA28 (Penn Station) and SH15 (Rockaway Park) is large.

        This is the anomalous segment that caused the original bug — ~25 km.
        """
        # SA28: 40.752287, -73.993391  SH15: 40.580903, -73.835592
        dist = _haversine_km(40.752287, -73.993391, 40.580903, -73.835592)
        assert dist > 20.0, f"SA28 to SH15 should be >20 km, got {dist:.2f}"


class TestIsSegmentAnomalous:
    """Test the anomalous segment detection function."""

    def test_normal_subway_segment_not_anomalous(self):
        """Test that a normal consecutive subway segment is not flagged."""
        # SH04 (Broad Channel) to SH12 (Beach 90 St) are adjacent on Rockaway Park branch
        assert not _is_segment_anomalous("SH04", "SH12", "SUBWAY")

    def test_cross_branch_subway_segment_anomalous(self):
        """Test that a cross-branch subway segment exceeding distance threshold is flagged.

        SA28 (Penn Station) to SH15 (Rockaway Park) spans ~25 km with no
        matching route — this should be caught as anomalous.
        """
        # NOTE: This specific segment now HAS a matching route (SUBWAY_A_ROCKAWAY),
        # so in practice get_canonical_segments would expand it. But the distance
        # check itself should still flag it if called directly.
        assert _is_segment_anomalous("SA28", "SH15", "SUBWAY")

    def test_njt_segments_not_checked(self):
        """Test that NJT segments are not subject to distance filtering."""
        # NY (Penn Station) and a distant NJT station — should not be flagged
        # because NJT is not in _MAX_UNMATCHED_SEGMENT_KM
        assert not _is_segment_anomalous("NY", "LB", "NJT")

    def test_unknown_station_not_anomalous(self):
        """Test that segments with unknown station codes are not flagged.

        If we can't look up coordinates, we can't determine distance,
        so we conservatively pass them through.
        """
        assert not _is_segment_anomalous("UNKNOWN1", "UNKNOWN2", "SUBWAY")


class TestAnomalousSegmentFiltering:
    """Test that anomalous segments are filtered during normalization."""

    def test_aggregated_anomalous_subway_segment_filtered(self):
        """Test that aggregated normalization filters anomalous unmatched subway segments.

        Creates a segment between two distant subway stations that don't share
        a route. The normalizer should drop it.
        """
        # S101 (Van Cortlandt Park-242 St, 1 train) and SH15 (Rockaway Park, A/H)
        # These are on completely different lines with no shared route, ~35 km apart
        raw = [
            SegmentCongestion(
                from_station="S101",
                to_station="SH15",
                data_source="SUBWAY",
                congestion_factor=1.0,
                congestion_level="normal",
                avg_transit_minutes=5.0,
                baseline_minutes=5.0,
                sample_count=1,
                average_delay_minutes=0.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)
        assert len(result) == 0, (
            f"Anomalous segment S101->SH15 should be filtered out, got {len(result)} segments"
        )

    def test_aggregated_valid_subway_segment_kept(self):
        """Test that valid unmatched subway segments are NOT filtered."""
        # Use two adjacent stations on the same line
        raw = [
            SegmentCongestion(
                from_station="SH04",
                to_station="SH12",
                data_source="SUBWAY",
                congestion_factor=1.1,
                congestion_level="normal",
                avg_transit_minutes=3.0,
                baseline_minutes=2.5,
                sample_count=5,
                average_delay_minutes=0.5,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)
        assert len(result) >= 1, "Valid segment SH04->SH12 should not be filtered"

    def test_individual_anomalous_subway_segment_filtered(self):
        """Test that individual normalization filters anomalous unmatched subway segments."""
        base_time = datetime(2025, 7, 15, 8, 0, 0)
        raw = [
            IndividualJourneySegment(
                journey_id="test-anomalous",
                train_id="A-999",
                from_station="S101",
                to_station="SH15",
                from_station_name="Van Cortlandt Park-242 St",
                to_station_name="Rockaway Park-Beach 116 St",
                data_source="SUBWAY",
                scheduled_departure=base_time,
                actual_departure=base_time,
                scheduled_arrival=base_time,
                actual_arrival=base_time,
                scheduled_minutes=60.0,
                actual_minutes=65.0,
                delay_minutes=5.0,
                congestion_factor=1.08,
                congestion_level="normal",
                is_cancelled=False,
                journey_date=date(2025, 7, 15),
            )
        ]
        result = normalize_individual_segments(raw)
        assert len(result) == 0, (
            f"Anomalous segment S101->SH15 should be filtered out, got {len(result)} segments"
        )
