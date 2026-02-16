"""
Unit tests for platform conversion logic in HistoricalTrackPredictor.

Tests the _convert_tracks_to_platforms method which aggregates individual
track probabilities into platform probabilities using station_configs mappings.
"""

import pytest

from trackrat.config.station_configs import get_platform_for_track, get_station_config
from trackrat.services.historical_track_predictor import HistoricalTrackPredictor


class TestConvertTracksToPlatforms:
    """Test _convert_tracks_to_platforms for various station types."""

    def setup_method(self) -> None:
        self.predictor = HistoricalTrackPredictor()

    def test_ny_penn_groups_paired_tracks(self) -> None:
        """NY Penn tracks 1 & 2 should combine into platform '1 & 2'."""
        track_probs = {"1": 0.3, "2": 0.2, "5": 0.5}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "NY")

        assert "1 & 2" in result
        assert result["1 & 2"] == pytest.approx(0.5)
        assert "5 & 6" in result
        assert result["5 & 6"] == pytest.approx(0.5)
        # Individual tracks should not appear
        assert "1" not in result
        assert "2" not in result
        assert "5" not in result

    def test_ny_penn_solo_track_17(self) -> None:
        """NY Penn track 17 is solo — maps to platform '17'."""
        track_probs = {"17": 0.6, "1": 0.4}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "NY")

        assert "17" in result
        assert result["17"] == pytest.approx(0.6)
        assert "1 & 2" in result
        assert result["1 & 2"] == pytest.approx(0.4)

    def test_gct_groups_upper_level_tracks(self) -> None:
        """GCT upper level tracks 36 & 37 should combine into a platform."""
        track_probs = {"36": 0.15, "37": 0.10, "38": 0.05}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "GCT")

        assert "36 & 37" in result
        assert result["36 & 37"] == pytest.approx(0.25)
        # Track 38 is solo
        assert "38" in result
        assert result["38"] == pytest.approx(0.05)

    def test_gct_groups_lower_level_tracks(self) -> None:
        """GCT lower level tracks 102 & 103 should combine."""
        track_probs = {"102": 0.3, "103": 0.2}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "GCT")

        assert "102 & 103" in result
        assert result["102 & 103"] == pytest.approx(0.5)

    def test_gct_lirr_madison_tracks_ungrouped(self) -> None:
        """LIRR Madison tracks (201+) have no platform mapping — pass through."""
        track_probs = {"201": 0.3, "202": 0.2, "36": 0.5}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "GCT")

        # LIRR tracks pass through as-is
        assert "201" in result
        assert result["201"] == pytest.approx(0.3)
        assert "202" in result
        assert result["202"] == pytest.approx(0.2)
        # MNR track gets grouped
        assert "36 & 37" in result
        assert result["36 & 37"] == pytest.approx(0.5)

    def test_gct_single_track_of_pair(self) -> None:
        """If only one track of a pair appears, it still maps to the pair name."""
        track_probs = {"42": 1.0}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "GCT")

        assert "41 & 42" in result
        assert result["41 & 42"] == pytest.approx(1.0)
        assert "42" not in result

    def test_station_without_platform_mappings_returns_as_is(self) -> None:
        """Stations like NP with no platform_mappings return tracks unchanged."""
        track_probs = {"1": 0.5, "2": 0.3, "3": 0.2}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "NP")

        assert result == track_probs

    def test_unknown_station_returns_as_is(self) -> None:
        """Unknown station codes use _default config (no mappings)."""
        track_probs = {"A": 0.5, "B": 0.5}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "UNKNOWN")

        assert result == track_probs

    def test_zero_probability_tracks_excluded(self) -> None:
        """Tracks with zero probability should not appear in output."""
        track_probs = {"1": 0.0, "2": 0.5, "3": 0.5}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "NY")

        # Track 1 has 0 prob, so "1 & 2" should only have track 2's prob
        assert "1 & 2" in result
        assert result["1 & 2"] == pytest.approx(0.5)

    def test_empty_probabilities(self) -> None:
        """Empty track probabilities should return empty dict."""
        result = self.predictor._convert_tracks_to_platforms({}, "NY")
        assert result == {}

    def test_gct_11_and_13_pair(self) -> None:
        """GCT tracks 11 & 13 pair (no track 12 historically)."""
        track_probs = {"13": 0.4}
        result = self.predictor._convert_tracks_to_platforms(track_probs, "GCT")

        assert "11 & 13" in result
        assert result["11 & 13"] == pytest.approx(0.4)


class TestGCTPlatformMappingsConfig:
    """Verify GCT platform_mappings in station_configs are correct."""

    def test_gct_has_platform_mappings(self) -> None:
        """GCT should have non-None platform_mappings."""
        config = get_station_config("GCT")
        assert config["platform_mappings"] is not None

    def test_gct_upper_level_pairs(self) -> None:
        """Verify all upper level track pairs."""
        expected_pairs = {
            "11": "11 & 13",
            "13": "11 & 13",
            "14": "14 & 15",
            "15": "14 & 15",
            "16": "16 & 17",
            "17": "16 & 17",
            "18": "18 & 19",
            "19": "18 & 19",
            "20": "20 & 21",
            "21": "20 & 21",
            "23": "23 & 24",
            "24": "23 & 24",
            "25": "25 & 26",
            "26": "25 & 26",
            "27": "27 & 28",
            "28": "27 & 28",
            "29": "29 & 30",
            "30": "29 & 30",
            "32": "32 & 33",
            "33": "32 & 33",
            "34": "34 & 35",
            "35": "34 & 35",
            "36": "36 & 37",
            "37": "36 & 37",
            "38": "38",
            "39": "39 & 40",
            "40": "39 & 40",
            "41": "41 & 42",
            "42": "41 & 42",
        }
        config = get_station_config("GCT")
        mappings = config["platform_mappings"]
        for track, expected_platform in expected_pairs.items():
            assert mappings[track] == expected_platform, (
                f"Track {track} should map to '{expected_platform}', "
                f"got '{mappings.get(track)}'"
            )

    def test_gct_lower_level_pairs(self) -> None:
        """Verify all lower level track pairs."""
        expected_pairs = {
            "102": "102 & 103",
            "103": "102 & 103",
            "104": "104 & 105",
            "105": "104 & 105",
            "106": "106 & 107",
            "107": "106 & 107",
            "111": "111 & 112",
            "112": "111 & 112",
            "113": "113 & 114",
            "114": "113 & 114",
        }
        config = get_station_config("GCT")
        mappings = config["platform_mappings"]
        for track, expected_platform in expected_pairs.items():
            assert mappings[track] == expected_platform, (
                f"Track {track} should map to '{expected_platform}', "
                f"got '{mappings.get(track)}'"
            )

    def test_gct_lirr_tracks_not_in_mappings(self) -> None:
        """LIRR Madison tracks (201+) should NOT be in platform_mappings."""
        config = get_station_config("GCT")
        mappings = config["platform_mappings"]
        lirr_tracks = ["201", "202", "204", "301", "302", "304"]
        for track in lirr_tracks:
            assert (
                track not in mappings
            ), f"LIRR track {track} should not be in platform_mappings"

    def test_get_platform_for_track_gct(self) -> None:
        """get_platform_for_track should work for GCT tracks."""
        assert get_platform_for_track("GCT", "36") == "36 & 37"
        assert get_platform_for_track("GCT", "38") == "38"
        assert get_platform_for_track("GCT", "102") == "102 & 103"
        # Unmapped LIRR track returns as-is
        assert get_platform_for_track("GCT", "201") == "201"

    def test_ny_still_has_platform_mappings(self) -> None:
        """NY Penn should still have its platform_mappings."""
        config = get_station_config("NY")
        assert config["platform_mappings"] is not None
        assert config["platform_mappings"]["1"] == "1 & 2"
