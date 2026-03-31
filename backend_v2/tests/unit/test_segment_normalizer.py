"""
Unit tests for the segment normalizer service.
"""

from datetime import date, datetime

from trackrat.models.api import IndividualJourneySegment
from trackrat.services.congestion_types import SegmentCongestion
from trackrat.services.segment_normalizer import (
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


class TestIsSegmentAnomalous:
    """Test the anomalous segment detection function.

    Anomaly detection for GTFS-RT systems checks whether both stations appear
    on the same route topology. Segments not on any route are anomalous
    (phantom cross-branch connections from sparse GTFS-RT data).
    """

    def test_normal_subway_segment_not_anomalous(self):
        """Test that a normal consecutive subway segment is not flagged.

        SH04 (Broad Channel) and SH12 (Beach 90 St) are both on the
        A/Rockaway line — they should NOT be flagged even though they're
        2.3 km apart.
        """
        assert not _is_segment_anomalous("SH04", "SH12", "SUBWAY")

    def test_same_route_subway_segment_not_anomalous(self):
        """Test that a skip-stop segment on a known route is not flagged.

        SA28 (Penn Station, A/C/E) and SH15 (Rockaway Park, A/S) are both
        on the A line route.
        """
        assert not _is_segment_anomalous("SA28", "SH15", "SUBWAY")

    def test_96st_to_astoria_ditmars_anomalous(self):
        """Test that 96 St (Q) to Astoria-Ditmars Blvd is flagged as anomalous.

        SQ05 (96 St on Q line) and SR01 (Astoria-Ditmars Blvd on N/W line)
        are on different branches with no shared route. Sparse GTFS-RT data
        can create a phantom segment between them.
        """
        assert _is_segment_anomalous("SQ05", "SR01", "SUBWAY")

    def test_bart_cross_branch_anomalous(self):
        """Test that BART cross-branch segments are flagged.

        BART_PLZA (El Cerrito Plaza, Red/Orange) and BART_WCRK (Walnut Creek,
        Yellow) are on different branches with no shared route.
        """
        assert _is_segment_anomalous("BART_PLZA", "BART_WCRK", "BART")

    def test_bart_same_route_not_anomalous(self):
        """Test that BART segments on a shared route are not flagged.

        BART_12TH and BART_19TH are adjacent on multiple BART routes.
        """
        assert not _is_segment_anomalous("BART_12TH", "BART_19TH", "BART")

    def test_lirr_cross_branch_anomalous(self):
        """Test that LIRR cross-branch segments are flagged.

        LHT (Long Beach) and QVG (Queens Village) are on different branches.
        """
        assert _is_segment_anomalous("LHT", "QVG", "LIRR")

    def test_lirr_same_route_not_anomalous(self):
        """Test that LIRR segments on a shared route are not flagged."""
        assert not _is_segment_anomalous("NY", "WDD", "LIRR")

    def test_njt_segments_not_checked(self):
        """Test that NJT segments are not subject to route-match filtering.

        NJT uses complete API stop lists, not sparse GTFS-RT data.
        """
        assert not _is_segment_anomalous("NY", "LB", "NJT")

    def test_non_gtfsrt_sources_not_checked(self):
        """Test that non-GTFS-RT sources without branching are not subject to route-match filtering.

        PATH and WMATA use complete route topology for stop creation.
        """
        assert not _is_segment_anomalous("UNKNOWN1", "UNKNOWN2", "PATH")
        assert not _is_segment_anomalous("UNKNOWN1", "UNKNOWN2", "WMATA")

    def test_amtrak_unknown_stations_are_anomalous(self):
        """Test that AMTRAK segments with unknown stations are flagged as anomalous.

        Amtrak API can return sparse stop lists creating phantom long-distance
        segments (e.g., NYP→BTN with missing intermediate stops).
        """
        assert _is_segment_anomalous("UNKNOWN1", "UNKNOWN2", "AMTRAK")

    def test_amtrak_valid_segment_not_anomalous(self):
        """Test that AMTRAK segments on known routes pass through."""
        # NEC segment: NY→TR is on the NEC route
        assert not _is_segment_anomalous("NY", "TR", "AMTRAK")
        # Vermonter segment: SPG→BRA is on the Vermonter route
        assert not _is_segment_anomalous("SPG", "BRA", "AMTRAK")


class TestAnomalousSegmentFiltering:
    """Test that anomalous segments are filtered during normalization."""

    def test_aggregated_anomalous_subway_segment_filtered(self):
        """Test that aggregated normalization filters anomalous unmatched subway segments.

        Creates a segment between two subway stations that don't share
        a route. The normalizer should drop it.
        """
        # SQ05 (96 St Q) and SR01 (Astoria-Ditmars Blvd N/W)
        # These are on different branches with no shared route
        raw = [
            SegmentCongestion(
                from_station="SQ05",
                to_station="SR01",
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
        assert (
            len(result) == 0
        ), f"Anomalous segment SQ05->SR01 should be filtered out, got {len(result)} segments"

    def test_aggregated_valid_subway_segment_kept(self):
        """Test that valid subway segments on a known route are NOT filtered."""
        # SH04 (Broad Channel) and SH12 (Beach 90 St) are adjacent on A/Rockaway
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
                train_id="Q-999",
                from_station="SQ05",
                to_station="SR01",
                from_station_name="96 St (Q)",
                to_station_name="Astoria-Ditmars Blvd",
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
        assert (
            len(result) == 0
        ), f"Anomalous segment SQ05->SR01 should be filtered out, got {len(result)} segments"


class TestEquivalenceResolutionInNormalization:
    """Test that station equivalences are resolved during segment normalization.

    Reproduces the actual bug: a train at Secaucus Lower Lvl (TS) heading to
    Pearl River (PQ) appeared as a single long congestion line instead of being
    decomposed into individual station hops via the Pascack Valley route.
    """

    def test_aggregated_ts_to_pq_expands_via_equivalence(self):
        """TS→PQ should expand to 14 Pascack Valley hops after resolving TS→SE."""
        raw = [
            SegmentCongestion(
                from_station="TS",
                to_station="PQ",
                data_source="NJT",
                congestion_factor=1.05,
                congestion_level="normal",
                avg_transit_minutes=45.0,
                baseline_minutes=43.0,
                sample_count=1,
                average_delay_minutes=2.0,
                cancellation_count=0,
                cancellation_rate=0.0,
            )
        ]
        result = normalize_aggregated_segments(raw)
        assert len(result) == 14, (
            f"TS→PQ should expand to 14 segments via Pascack Valley "
            f"(SE→WR, WR→TE, ..., ZM→PQ), got {len(result)}: "
            f"{[(s.from_station, s.to_station) for s in result]}"
        )
        # First segment should start from SE (the resolved topology code)
        assert (
            result[0].from_station == "SE"
        ), f"First expanded segment should start from SE, got {result[0].from_station}"
        # Last segment should end at PQ
        assert (
            result[-1].to_station == "PQ"
        ), f"Last expanded segment should end at PQ, got {result[-1].to_station}"
        # All segments should carry the original data source
        for seg in result:
            assert seg.data_source == "NJT"

    def test_individual_ts_to_pq_expands_via_equivalence(self):
        """Individual segment TS→PQ should also expand via equivalence."""
        base_time = datetime(2026, 3, 30, 12, 0, 0)
        raw = [
            IndividualJourneySegment(
                journey_id="1",
                train_id="1234",
                from_station="TS",
                to_station="PQ",
                from_station_name="Secaucus Lower Lvl",
                to_station_name="Pearl River",
                data_source="NJT",
                scheduled_departure=base_time,
                actual_departure=base_time,
                scheduled_arrival=base_time,
                actual_arrival=base_time,
                scheduled_minutes=45.0,
                actual_minutes=47.0,
                delay_minutes=2.0,
                congestion_factor=1.05,
                congestion_level="normal",
                is_cancelled=False,
                journey_date=date(2026, 3, 30),
            )
        ]
        result = normalize_individual_segments(raw)
        assert len(result) == 14, (
            f"Individual TS→PQ should expand to 14 segments, "
            f"got {len(result)}: {[(s.from_station, s.to_station) for s in result]}"
        )
        # All segments should have the same journey/train info
        for seg in result:
            assert seg.journey_id == "1"
            assert seg.train_id == "1234"
            assert seg.data_source == "NJT"
