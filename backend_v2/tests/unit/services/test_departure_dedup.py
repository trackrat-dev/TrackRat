"""
Unit tests for departure deduplication logic.

Tests the _make_dedup_keys and _merge_departures functions to ensure
GTFS scheduled data and real-time API data are properly deduplicated.

Key scenarios:
1. Matching by train_id (primary key)
2. Matching by line+time (fallback key)
3. NJT line code normalization (GTFS "NEC" vs API "NE")
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
            line_code="No",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        primary, fallback = self.service._make_dedup_keys(departure)

        assert primary == "3936:2026-01-20:NJT"

    def test_fallback_key_format(self):
        """Test fallback key includes line code, source, and time."""
        departure = self._create_departure(
            train_id="3936",
            line_code="No",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="NJT",
        )

        primary, fallback = self.service._make_dedup_keys(departure)

        assert fallback == "No:NJT:09:15"

    def test_no_primary_key_when_train_id_missing(self):
        """Test no primary key when train_id is empty."""
        departure = self._create_departure(
            train_id="",
            line_code="No",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
        )

        primary, fallback = self.service._make_dedup_keys(departure)

        assert primary is None
        assert fallback == "No:NJT:09:15"

    def test_no_primary_key_when_train_id_unknown(self):
        """Test no primary key when train_id is 'Unknown'."""
        departure = self._create_departure(
            train_id="Unknown",
            line_code="No",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
        )

        primary, fallback = self.service._make_dedup_keys(departure)

        assert primary is None

    def test_amtrak_train_id_normalized(self):
        """Test Amtrak train_id has 'A' prefix stripped."""
        departure = self._create_departure(
            train_id="A2205",
            line_code="AM",
            scheduled_time=ET.localize(datetime(2026, 1, 20, 9, 15)),
            data_source="AMTRAK",
        )

        primary, fallback = self.service._make_dedup_keys(departure)

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
            line_code="No",
            scheduled_time=time_in_et,
            data_source="NJT",
        )
        departure_utc = self._create_departure(
            train_id="3846",
            line_code="No",
            scheduled_time=time_in_utc,
            data_source="NJT",
        )

        _, fallback_et = self.service._make_dedup_keys(departure_et)
        _, fallback_utc = self.service._make_dedup_keys(departure_utc)

        # Both should produce the same fallback key (13:03 in ET)
        assert fallback_et == "No:NJT:13:03"
        assert fallback_utc == "No:NJT:13:03"
        assert fallback_et == fallback_utc


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
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
        ]
        gtfs = [
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
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
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
        ]
        # GTFS uses gtfs_trip_id as train_id
        gtfs = [
            self._create_departure(train_id="2508", line_code="No", scheduled_time=time)
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should only have 1 train (real-time) because fallback key matches
        assert len(merged) == 1
        assert merged[0].train_id == "3936"

    def test_line_code_must_match_for_dedup(self):
        """Test that different line codes don't deduplicate.

        This is the key bug scenario: if GTFS uses "NEC" and real-time uses "No",
        the fallback keys won't match and we get duplicates.

        After the fix, GTFS is normalized to "No" via NJT_LINE_CODE_MAPPING.
        """
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # Real-time uses API line code "No" (from "Northeast Corridor" truncated)
        realtime = [
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
        ]
        # If GTFS wasn't normalized, it would use "NEC" - causing duplicates
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="NEC", scheduled_time=time
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # WITHOUT line code normalization: 2 trains (duplicate!)
        # WITH line code normalization: 1 train (correct)
        # This test documents the problem - GTFS must use normalized line codes
        assert len(merged) == 2  # Documents the mismatch case

    def test_normalized_line_codes_dedup_correctly(self):
        """Test that normalized line codes enable correct deduplication."""
        time = ET.localize(datetime(2026, 1, 20, 9, 15))

        # Both use normalized line code "No" (after GTFS NEC -> No mapping)
        realtime = [
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="No", scheduled_time=time
            )  # After NJT_LINE_CODE_MAPPING: NEC -> No
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # With same line codes, fallback key matches - no duplicates
        assert len(merged) == 1

    def test_gtfs_added_when_no_realtime_match(self):
        """Test GTFS trains are added when no real-time match exists."""
        time1 = ET.localize(datetime(2026, 1, 20, 9, 15))
        time2 = ET.localize(datetime(2026, 1, 20, 10, 15))

        realtime = [
            self._create_departure(
                train_id="3936", line_code="No", scheduled_time=time1
            )
        ]
        gtfs = [
            self._create_departure(
                train_id="2508", line_code="No", scheduled_time=time2
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
                train_id="3936", line_code="No", scheduled_time=time, is_cancelled=True
            )
        ]
        gtfs = [
            self._create_departure(train_id="3936", line_code="No", scheduled_time=time)
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
                train_id="3846", line_code="No", scheduled_time=time_utc
            )
        ]
        # GTFS train with ET time (same moment)
        gtfs = [
            self._create_departure(
                train_id="2483", line_code="No", scheduled_time=time_et
            )
        ]

        merged = self.service._merge_departures(realtime, gtfs)

        # Should deduplicate to 1 train (real-time preferred)
        assert len(merged) == 1
        assert merged[0].train_id == "3846"  # Real-time train wins
