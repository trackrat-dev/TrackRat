"""
Unit tests for departure deduplication logic.

Tests the _make_dedup_keys and _merge_departures functions to ensure
GTFS scheduled data and real-time API data are properly deduplicated.

Key scenarios:
1. Matching by train_id (primary key)
2. Matching by line+time (fallback key)
3. NJT line code normalization (legacy "No" vs current "NE")
4. Amtrak train_id normalization (strip "A" prefix)
"""

from datetime import date, datetime

import pytest
from unittest.mock import MagicMock

from trackrat.models.api import (
    DataFreshness,
    LineInfo,
    StationInfo,
    TrainDeparture,
    TrainPosition,
)
from trackrat.services.departure import DepartureService, _destination_prefix
from trackrat.utils.time import ET


class TestDestinationPrefix:
    """Tests for the _destination_prefix helper."""

    def test_returns_lowercase_first_word(self):
        assert _destination_prefix("Suffern") == "suffern"

    def test_handles_via_suffix(self):
        assert _destination_prefix("Suffern via Hoboken") == "suffern"

    def test_handles_leading_whitespace(self):
        assert _destination_prefix("  Suffern ") == "suffern"

    def test_empty_string_for_none(self):
        assert _destination_prefix(None) == ""

    def test_empty_string_for_empty(self):
        assert _destination_prefix("") == ""

    def test_distinct_termini_compare_unequal(self):
        assert _destination_prefix("Suffern") != _destination_prefix("Port Jervis")


class TestMakeDedupKeys:
    """Tests for _make_dedup_keys function."""

    def setup_method(self):
        # Create a minimal DepartureService without database
        self.service = DepartureService.__new__(DepartureService)

    def _create_departure(
        self,
        train_id: str,
        line_code: str,
        scheduled_time: datetime,
        data_source: str = "NJT",
        journey_date: date | None = None,
        is_cancelled: bool = False,
    ) -> TrainDeparture:
        """Create a TrainDeparture for testing."""
        return TrainDeparture(
            train_id=train_id,
            journey_date=journey_date or scheduled_time.date(),
            line=LineInfo(code=line_code, name="Test Line", color="#000000"),
            destination="Test Destination",
            departure=StationInfo(
                code="NY",
                name="New York Penn Station",
                scheduled_time=scheduled_time,
                updated_time=None,
                actual_time=None,
                track=None,
            ),
            arrival=None,
            train_position=TrainPosition(
                last_departed_station_code=None,
                at_station_code=None,
                next_station_code=None,
                between_stations=False,
            ),
            data_freshness=DataFreshness(
                last_updated=scheduled_time,
                age_seconds=0,
                update_count=None,
                collection_method=None,
            ),
            data_source=data_source,
            is_cancelled=is_cancelled,
        )

    def test_primary_key_format(self):
        """Test primary key includes train_id, date, and source."""
        departure = self._create_departure(
            train_id="3936",
            line_code="NE",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        primary, fallbacks = self.service._make_dedup_keys(departure)

        assert primary == "3936:2026-01-20:NJT"

    def test_fallback_keys_include_time_tolerance(self):
        """Test fallback keys include current time and ±1 minute for tolerance."""
        departure = self._create_departure(
            train_id="3936",
            line_code="NE",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        primary, fallbacks = self.service._make_dedup_keys(departure)

        # Should have 3 keys: 09:14, 09:15, 09:16
        assert len(fallbacks) == 3
        assert "NE:NJT:09:14" in fallbacks
        assert "NE:NJT:09:15" in fallbacks
        assert "NE:NJT:09:16" in fallbacks

    def test_no_primary_key_when_train_id_missing(self):
        """Test no primary key when train_id is empty."""
        departure = self._create_departure(
            train_id="",
            line_code="NE",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
        )

        primary, fallbacks = self.service._make_dedup_keys(departure)

        assert primary is None
        assert "NE:NJT:09:15" in fallbacks

    def test_no_primary_key_when_train_id_unknown(self):
        """Test no primary key when train_id is 'Unknown'."""
        departure = self._create_departure(
            train_id="Unknown",
            line_code="NE",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
        )

        primary, fallbacks = self.service._make_dedup_keys(departure)

        assert primary is None

    def test_amtrak_train_id_normalized(self):
        """Test Amtrak train_id has 'A' prefix stripped."""
        departure = self._create_departure(
            train_id="A2205",
            line_code="AM",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="AMTRAK",
        )

        primary, fallbacks = self.service._make_dedup_keys(departure)

        # A2205 should become 2205 in the key
        assert primary == "2205:2026-01-20:AMTRAK"

    def test_fallback_key_normalizes_timezone_to_et(self):
        """Test fallback key uses ET time regardless of input timezone.

        This is critical for deduplication: GTFS times are stored in ET,
        while real-time API times may be in UTC. Both should produce the
        same fallback key for the same moment in time.
        """
        from zoneinfo import ZoneInfo

        # Same moment: 13:03 ET = 18:03 UTC
        time_in_et = ET.localize(datetime(2026, 1, 20, 13, 3))
        time_in_utc = datetime(2026, 1, 20, 18, 3, tzinfo=ZoneInfo("UTC"))

        departure_et = self._create_departure(
            train_id="2483",
            line_code="NE",
            scheduled_time=time_in_et,
            data_source="NJT",
        )
        departure_utc = self._create_departure(
            train_id="3846",
            line_code="NE",
            scheduled_time=time_in_utc,
            data_source="NJT",
        )

        _, fallbacks_et = self.service._make_dedup_keys(departure_et)
        _, fallbacks_utc = self.service._make_dedup_keys(departure_utc)

        # Both should produce the same fallback keys (13:02, 13:03, 13:04 in ET)
        assert "NE:NJT:13:03" in fallbacks_et
        assert "NE:NJT:13:03" in fallbacks_utc
        # The main key should be the same
        assert fallbacks_et == fallbacks_utc

    def test_njt_legacy_no_code_canonicalized_to_ne(self):
        """Test legacy NJT line code 'No' is canonicalized to 'NE'.

        'No' was produced by the old schedule collector truncating
        "Northeast Corridor" to 2 chars. Existing DB records may still
        have this value, so the canonicalization maps it to 'NE' for dedup.
        """
        departure = self._create_departure(
            train_id="3936",
            line_code="No",  # Legacy truncated code
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        _, fallbacks = self.service._make_dedup_keys(departure)

        # "No" should be canonicalized to "NE"
        assert "NE:NJT:09:15" in fallbacks
        assert "No:NJT:09:15" not in fallbacks

    def test_njt_line_code_rv_stays_rv(self):
        """Test NJT line code 'RV' is already canonical (no normalization needed)."""
        departure = self._create_departure(
            train_id="5409",
            line_code="RV",  # From NJT API — now matches GTFS directly
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        _, fallbacks = self.service._make_dedup_keys(departure)

        # "RV" is already canonical, should appear as-is
        assert "RV:NJT:09:15" in fallbacks

    def test_non_njt_line_codes_not_normalized(self):
        """Test that non-NJT line codes are not affected by normalization."""
        departure = self._create_departure(
            train_id="A2205",
            line_code="NE",  # Same code but for Amtrak
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="AMTRAK",
        )

        _, fallbacks = self.service._make_dedup_keys(departure)

        # AMTRAK "NE" should NOT be normalized (it's a different system)
        assert "NE:AMTRAK:09:15" in fallbacks


class TestMergeDepartures:
    """Tests for _merge_departures function."""

    def setup_method(self):
        # Create a minimal DepartureService without database
        self.service = DepartureService.__new__(DepartureService)

    def _create_departure(
        self,
        train_id: str,
        line_code: str,
        scheduled_time: datetime,
        data_source: str = "NJT",
        is_cancelled: bool = False,
    ) -> TrainDeparture:
        """Create a TrainDeparture for testing."""
        return TrainDeparture(
            train_id=train_id,
            journey_date=scheduled_time.date(),
            line=LineInfo(code=line_code, name="Test Line", color="#000000"),
            destination="Test Destination",
            departure=StationInfo(
                code="NY",
                name="New York Penn Station",
                scheduled_time=scheduled_time,
                updated_time=None,
                actual_time=None,
                track=None,
            ),
            arrival=None,
            train_position=TrainPosition(
                last_departed_station_code=None,
                at_station_code=None,
                next_station_code=None,
                between_stations=False,
            ),
            data_freshness=DataFreshness(
                last_updated=scheduled_time,
                age_seconds=0,
                update_count=None,
                collection_method=None,
            ),
            data_source=data_source,
            is_cancelled=is_cancelled,
        )

    def test_realtime_preferred_over_gtfs_by_train_id(self):
        """Test real-time train with same train_id blocks GTFS duplicate."""
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        realtime = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]
        gtfs = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should only have 1 train (real-time)
        assert len(merged) == 1
        assert merged[0].train_id == "3936"

    def test_realtime_preferred_over_gtfs_by_line_time(self):
        """Test real-time train blocks GTFS with same line+time (fallback key)."""
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # Real-time has different train_id but same line+time
        realtime = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]
        # GTFS uses gtfs_trip_id as train_id
        gtfs = [
            self._create_departure(train_id="2508", line_code="NE", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should only have 1 train (real-time) because fallback key matches
        assert len(merged) == 1
        assert merged[0].train_id == "3936"

    def test_line_code_normalization_enables_dedup(self):
        """Test that line code normalization enables correct deduplication.

        NJT API sometimes returns 'RV' for Raritan Valley while GTFS maps to 'Ra'.
        With normalization, 'RV' -> 'Ra' and they correctly deduplicate.
        """
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # GTFS uses canonical line code "Ra"
        realtime = [
            self._create_departure(train_id="5409", line_code="Ra", scheduled_time=time)
        ]
        # API returns "RV" which normalizes to "Ra"
        gtfs = [
            self._create_departure(train_id="5410", line_code="RV", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # With line code normalization: 1 train (correctly deduplicated)
        assert len(merged) == 1
        assert merged[0].train_id == "5409"  # Real-time preferred

    def test_normalized_line_codes_dedup_correctly(self):
        """Test that matching line codes enable correct deduplication."""
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # Both use line code "NE" (API and GTFS now both produce "NE" for NEC)
        realtime = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="NE", scheduled_time=time
            )  # After NJT_LINE_CODE_MAPPING: NEC -> NE
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # With same line codes, fallback key matches - no duplicates
        assert len(merged) == 1

    def test_time_tolerance_deduplicates_within_one_minute(self):
        """Test that trains within 1 minute of each other deduplicate.

        Schedule differences between GTFS and real-time API can cause
        the same train to have slightly different scheduled times.
        With ±1 minute tolerance, these should still deduplicate.
        """
        realtime_time = ET.localize(datetime(2026, 1, 20, 9, 15))
        gtfs_time = ET.localize(datetime(2026, 1, 20, 9, 16))  # 1 minute later

        realtime = [
            self._create_departure(
                train_id="3936", line_code="NE", scheduled_time=realtime_time
            )
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="NE", scheduled_time=gtfs_time
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should deduplicate despite 1 minute difference
        assert len(merged) == 1
        assert merged[0].train_id == "3936"

    def test_time_tolerance_does_not_dedup_beyond_one_minute(self):
        """Test that trains more than 1 minute apart don't deduplicate."""
        realtime_time = ET.localize(datetime(2026, 1, 20, 9, 15))
        gtfs_time = ET.localize(datetime(2026, 1, 20, 9, 18))  # 3 minutes later

        realtime = [
            self._create_departure(
                train_id="3936", line_code="NE", scheduled_time=realtime_time
            )
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="NE", scheduled_time=gtfs_time
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should NOT deduplicate - 3 minutes is beyond tolerance
        assert len(merged) == 2

    def test_gtfs_added_when_no_realtime_match(self):
        """Test GTFS trains are added when no real-time match exists."""
        time1 = ET.localize(datetime(2026, 1, 20, 9, 15))
        time2 = ET.localize(datetime(2026, 1, 20, 10, 15))

        realtime = [
            self._create_departure(
                train_id="3936", line_code="NE", scheduled_time=time1
            )
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="NE", scheduled_time=time2
            )  # Different time
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Both trains should be present (different times)
        assert len(merged) == 2

    def test_cancelled_train_suppresses_gtfs(self):
        """Test cancelled real-time trains suppress GTFS counterparts."""
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        realtime = [
            self._create_departure(
                train_id="3936", line_code="NE", scheduled_time=time, is_cancelled=True
            )
        ]
        gtfs = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # GTFS train should not appear (suppressed by cancelled real-time)
        assert len(merged) == 1
        assert merged[0].is_cancelled is True

    def test_dedup_works_across_timezones(self):
        """Test that trains at same time but different timezones deduplicate.

        Real-world scenario: GTFS times are in ET, real-time API times are in UTC.
        Train 2483 (GTFS) at 13:03 ET should deduplicate with
        Train 3846 (real-time) at 18:03 UTC (same moment).
        """
        from zoneinfo import ZoneInfo

        # Same moment: 13:03 ET = 18:03 UTC
        time_et = ET.localize(datetime(2026, 1, 20, 13, 3))
        time_utc = datetime(2026, 1, 20, 18, 3, tzinfo=ZoneInfo("UTC"))

        # Real-time train with UTC time
        realtime = [
            self._create_departure(
                train_id="3846", line_code="NE", scheduled_time=time_utc
            )
        ]
        # GTFS train with ET time (same moment)
        gtfs = [
            self._create_departure(
                train_id="2483", line_code="NE", scheduled_time=time_et
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should deduplicate to 1 train (real-time preferred)
        assert len(merged) == 1
        assert merged[0].train_id == "3846"  # Real-time train wins

    def test_legacy_no_code_deduplicates_with_gtfs_ne(self):
        """Test that legacy 'No' line code in DB deduplicates with GTFS 'NE'.

        Real-world scenario: Train 3719 in DB has line_code 'No' (from schedule
        collector truncating 'Northeast Corridor'). GTFS train 3243 has line_code
        'NE' (from NJT_LINE_CODE_MAPPING). These are the same physical train
        at the same time. With canonicalization, 'No' → 'NE' enables dedup.
        """
        time = ET.localize(datetime(2026, 2, 26, 14, 52))

        # DB train with legacy "No" code (from schedule collector)
        realtime = [
            self._create_departure(train_id="3719", line_code="No", scheduled_time=time)
        ]
        # GTFS train with correct "NE" code
        gtfs = [
            self._create_departure(train_id="3243", line_code="NE", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should deduplicate: "No" canonicalizes to "NE", matching GTFS
        assert len(merged) == 1
        assert merged[0].train_id == "3719"  # DB train preferred


class TestDedupeScheduledObservedCollisions:
    """Tests for _dedupe_scheduled_observed_collisions.

    Covers the issue where NJT publishes different train numbers in the
    schedule API vs the real-time feed, leaving two TrainJourney rows
    for the same physical train (one SCHEDULED, one OBSERVED) that the
    train_id-only dedup above can't collapse.
    """

    def setup_method(self):
        self.service = DepartureService.__new__(DepartureService)

    def _create_departure(
        self,
        train_id: str,
        line_code: str,
        scheduled_time: datetime,
        observation_type: str = "OBSERVED",
        destination: str = "Suffern",
        data_source: str = "NJT",
    ) -> TrainDeparture:
        return TrainDeparture(
            train_id=train_id,
            journey_date=scheduled_time.date(),
            line=LineInfo(code=line_code, name="Bergen", color="#000000"),
            destination=destination,
            departure=StationInfo(
                code="HB",
                name="Hoboken",
                scheduled_time=scheduled_time,
                updated_time=None,
                actual_time=None,
                track=None,
            ),
            arrival=None,
            train_position=TrainPosition(
                last_departed_station_code=None,
                at_station_code=None,
                next_station_code=None,
                between_stations=False,
            ),
            data_freshness=DataFreshness(
                last_updated=scheduled_time,
                age_seconds=0,
                update_count=None,
                collection_method=None,
            ),
            data_source=data_source,
            observation_type=observation_type,
        )

    def test_drops_scheduled_when_observed_at_same_line_and_time(self):
        """The reported HB→GK case: 1-min drift, same line, drop SCHEDULED."""
        observed_time = ET.localize(datetime(2026, 5, 17, 12, 30))
        scheduled_time = ET.localize(datetime(2026, 5, 17, 12, 31))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=observed_time,
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=scheduled_time,
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 1
        assert result[0].train_id == "1234"
        assert result[0].observation_type == "OBSERVED"

    def test_keeps_scheduled_when_destination_does_not_match(self):
        """Same line + time but different terminus: legitimately different trains."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=time,
                observation_type="OBSERVED",
                destination="Suffern",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=time,
                observation_type="SCHEDULED",
                destination="Port Jervis",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        # Different destinations — both should survive.
        assert len(result) == 2

    def test_matches_destination_with_via_suffix(self):
        """NJT 'Suffern' vs 'Suffern via Hoboken' should still match."""
        observed_time = ET.localize(datetime(2026, 5, 17, 12, 30))
        scheduled_time = ET.localize(datetime(2026, 5, 17, 12, 31))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=observed_time,
                observation_type="OBSERVED",
                destination="Suffern via Hoboken",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=scheduled_time,
                observation_type="SCHEDULED",
                destination="Suffern",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 1
        assert result[0].train_id == "1234"

    def test_does_not_collapse_two_observed_rows(self):
        """Two OBSERVED rows at same line/time are presumed real distinct trains."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=time,
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=time,
                observation_type="OBSERVED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 2

    def test_does_not_collapse_two_scheduled_rows(self):
        """Two SCHEDULED rows at same line/time are preserved (no OBSERVED anchor)."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=time,
                observation_type="SCHEDULED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=time,
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 2

    def test_does_not_collapse_across_different_lines(self):
        """Different lines at the same time are clearly different trains."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=time,
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="NE",
                scheduled_time=time,
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 2

    def test_does_not_collapse_across_data_sources(self):
        """Different data sources are independent — never cross-merge."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="NE",
                scheduled_time=time,
                observation_type="OBSERVED",
                data_source="NJT",
            ),
            self._create_departure(
                train_id="A2205",
                line_code="NE",
                scheduled_time=time,
                observation_type="SCHEDULED",
                data_source="AMTRAK",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert len(result) == 2

    def test_returns_input_unchanged_when_no_observed_rows(self):
        """All-SCHEDULED input bypasses the function early — no work done."""
        time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=time,
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert result is deps  # short-circuited

    def test_drift_beyond_two_minutes_does_not_collapse(self):
        """A SCHEDULED row 3 minutes off the OBSERVED stays — outside tolerance."""
        observed_time = ET.localize(datetime(2026, 5, 17, 12, 30))
        scheduled_time = ET.localize(datetime(2026, 5, 17, 12, 33))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=observed_time,
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=scheduled_time,
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        # ±1 min on each side overlaps at 12:31 only; 12:33 falls outside.
        assert len(result) == 2

    def test_one_observed_collapses_multiple_matching_scheduled(self):
        """An OBSERVED row drops all colliding SCHEDULED rows in its bucket."""
        observed_time = ET.localize(datetime(2026, 5, 17, 12, 30))

        deps = [
            self._create_departure(
                train_id="1234",
                line_code="BE",
                scheduled_time=observed_time,
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="5678",
                line_code="BE",
                scheduled_time=ET.localize(datetime(2026, 5, 17, 12, 29)),
                observation_type="SCHEDULED",
            ),
            self._create_departure(
                train_id="9012",
                line_code="BE",
                scheduled_time=ET.localize(datetime(2026, 5, 17, 12, 31)),
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        # Both SCHEDULED rows share a ±1 min key with the OBSERVED row AND
        # the same destination — they collapse.
        assert len(result) == 1
        assert result[0].train_id == "1234"

    def test_preserves_order_of_surviving_departures(self):
        """Function should not reorder surviving departures."""
        deps = [
            self._create_departure(
                train_id="A",
                line_code="BE",
                scheduled_time=ET.localize(datetime(2026, 5, 17, 12, 0)),
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="B",
                line_code="BE",
                scheduled_time=ET.localize(datetime(2026, 5, 17, 13, 0)),
                observation_type="OBSERVED",
            ),
            self._create_departure(
                train_id="C",
                line_code="BE",
                scheduled_time=ET.localize(datetime(2026, 5, 17, 14, 0)),
                observation_type="SCHEDULED",
            ),
        ]

        result = self.service._dedupe_scheduled_observed_collisions(deps)

        assert [d.train_id for d in result] == ["A", "B", "C"]
