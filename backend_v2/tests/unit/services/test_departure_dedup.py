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
from trackrat.services.departure import DepartureService
from trackrat.utils.time import ET


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

    def test_njt_line_code_normalization_no_to_ne(self):
        """Test legacy NJT line code 'No' is normalized to 'NE' for deduplication.

        Some DB records may have the old 'No' code from prior truncation-based
        mapping. The canonicalization normalizes 'No' -> 'NE' so they match
        current data which uses 'NE'.
        """
        departure = self._create_departure(
            train_id="3936",
            line_code="No",  # Legacy code from old mapping
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        _, fallbacks = self.service._make_dedup_keys(departure)

        # "No" should be normalized to "NE" in the fallback key
        assert "NE:NJT:09:15" in fallbacks
        assert "No:NJT:09:15" not in fallbacks

    def test_njt_line_code_normalization_rv_to_ra(self):
        """Test NJT line code 'RV' is normalized to 'Ra' for deduplication."""
        departure = self._create_departure(
            train_id="5409",
            line_code="RV",  # From NJT API
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        _, fallbacks = self.service._make_dedup_keys(departure)

        # "RV" should be normalized to "Ra"
        assert "Ra:NJT:09:15" in fallbacks

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

        Legacy DB records may have 'No' while current data uses 'NE'.
        With normalization, 'No' -> 'NE' and they correctly deduplicate.
        """
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # Real-time uses API line code "NE"
        realtime = [
            self._create_departure(train_id="3936", line_code="NE", scheduled_time=time)
        ]
        # Legacy record might have "No"
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="No", scheduled_time=time
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # With line code normalization: 1 train (correctly deduplicated)
        assert len(merged) == 1
        assert merged[0].train_id == "3936"  # Real-time preferred

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
