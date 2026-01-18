"""
Unit tests for GTFS static schedule service.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from trackrat.services.gtfs import (
    GTFSService,
    GTFS_DOWNLOAD_INTERVAL_HOURS,
)
from trackrat.models.database import (
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
)
from trackrat.utils.time import ET


class TestGTFSTimeParsing:
    """Tests for GTFS time parsing helper."""

    def setup_method(self):
        self.service = GTFSService()

    def test_parse_normal_time(self):
        """Test parsing normal HH:MM:SS time."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("14:30:00", target_date)

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0
        assert result.date() == target_date

    def test_parse_overnight_time(self):
        """Test parsing times >= 24:00 for overnight trips."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("25:30:00", target_date)

        assert result is not None
        assert result.hour == 1
        assert result.minute == 30
        # Should be next day
        assert result.date() == date(2026, 1, 21)

    def test_parse_late_overnight_time(self):
        """Test parsing times like 26:15 (2:15 AM next day)."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("26:15:00", target_date)

        assert result is not None
        assert result.hour == 2
        assert result.minute == 15
        assert result.date() == date(2026, 1, 21)

    def test_parse_empty_time(self):
        """Test parsing empty time string returns None."""
        result = self.service._parse_gtfs_time("", date(2026, 1, 20))
        assert result is None

    def test_parse_invalid_time(self):
        """Test parsing invalid time string returns None."""
        result = self.service._parse_gtfs_time("invalid", date(2026, 1, 20))
        assert result is None

    def test_parse_time_without_seconds(self):
        """Test parsing HH:MM format (no seconds)."""
        result = self.service._parse_gtfs_time("14:30", date(2026, 1, 20))

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0


class TestGTFSDateParsing:
    """Tests for GTFS date parsing helper."""

    def setup_method(self):
        self.service = GTFSService()

    def test_parse_valid_date(self):
        """Test parsing YYYYMMDD format."""
        result = self.service._parse_gtfs_date("20260120")

        assert result == date(2026, 1, 20)

    def test_parse_empty_date(self):
        """Test parsing empty date returns today."""
        result = self.service._parse_gtfs_date("")

        assert result == date.today()

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns today."""
        result = self.service._parse_gtfs_date("invalid")

        assert result == date.today()


class TestTrainIdExtraction:
    """Tests for train ID extraction from headsign."""

    def setup_method(self):
        self.service = GTFSService()

    def test_extract_train_id_with_number(self):
        """Test extracting train number from headsign."""
        result = self.service._extract_train_id("Train 3245 to Trenton")
        assert result == "3245"

    def test_extract_train_id_number_only(self):
        """Test extracting when headsign is just a number."""
        result = self.service._extract_train_id("3840")
        assert result == "3840"

    def test_extract_train_id_no_number(self):
        """Test returns None when no train number in headsign."""
        result = self.service._extract_train_id("To Trenton")
        assert result is None

    def test_extract_train_id_empty(self):
        """Test returns None for empty headsign."""
        result = self.service._extract_train_id("")
        assert result is None


class TestRateLimiting:
    """Tests for GTFS download rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_prevents_recent_download(self):
        """Test that download is skipped if recently downloaded."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 1 hour ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(hours=1)

        mock_db = AsyncMock()

        with patch.object(
            service, "_get_or_create_feed_info", return_value=mock_feed_info
        ):
            result = await service.refresh_feed(mock_db, "NJT", force=False)

        # Should return False (skipped due to rate limit)
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_allows_old_download(self):
        """Test that download is allowed if last download was long ago."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 25 hours ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(hours=25)

        mock_db = AsyncMock()

        # We need to mock the actual HTTP download and parsing
        with (
            patch.object(
                service, "_get_or_create_feed_info", return_value=mock_feed_info
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(service, "_parse_and_store_gtfs", return_value={}),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = b"mock zip content"
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()

            result = await service.refresh_feed(mock_db, "NJT", force=False)

        # Should return True (download was performed)
        assert result is True

    @pytest.mark.asyncio
    async def test_force_bypasses_rate_limit(self):
        """Test that force=True bypasses rate limiting."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 1 minute ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(minutes=1)

        mock_db = AsyncMock()

        with (
            patch.object(
                service, "_get_or_create_feed_info", return_value=mock_feed_info
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(service, "_parse_and_store_gtfs", return_value={}),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = b"mock zip content"
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()

            result = await service.refresh_feed(mock_db, "NJT", force=True)

        # Should return True despite recent download because force=True
        assert result is True


class TestActiveServiceIds:
    """Tests for determining active service IDs on a given date."""

    @pytest.mark.asyncio
    async def test_weekday_service(self):
        """Test getting active services for a weekday."""
        service = GTFSService()

        # Monday = 0
        target_date = date(2026, 1, 19)  # This is a Monday

        mock_db = AsyncMock()

        # Mock calendar query result
        mock_result = MagicMock()
        mock_result.all.return_value = [("SERVICE_WEEKDAY",)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Second call for calendar_dates should return empty
        async def mock_execute(query):
            result = MagicMock()
            # First call is calendar, second is calendar_dates
            if "gtfs_calendar_dates" in str(query):
                result.all.return_value = []
            else:
                result.all.return_value = [("SERVICE_WEEKDAY",)]
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        assert "SERVICE_WEEKDAY" in result

    @pytest.mark.asyncio
    async def test_service_exception_added(self):
        """Test that calendar_dates additions are included."""
        service = GTFSService()
        target_date = date(2026, 1, 20)

        mock_db = AsyncMock()

        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Calendar query - no regular service
                result.all.return_value = []
            else:
                # Calendar dates query - service added for this date
                result.all.return_value = [("SPECIAL_SERVICE", 1)]  # exception_type=1 means added
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        assert "SPECIAL_SERVICE" in result

    @pytest.mark.asyncio
    async def test_service_exception_removed(self):
        """Test that calendar_dates removals are excluded."""
        service = GTFSService()
        target_date = date(2026, 1, 20)

        mock_db = AsyncMock()

        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Calendar query - regular service
                result.all.return_value = [("REGULAR_SERVICE",)]
            else:
                # Calendar dates query - service removed for this date
                result.all.return_value = [("REGULAR_SERVICE", 2)]  # exception_type=2 means removed
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        # Service should be removed
        assert "REGULAR_SERVICE" not in result


class TestStationMapping:
    """Tests for GTFS station mapping functions."""

    def test_amtrak_station_mapping(self):
        """Test mapping Amtrak GTFS stop_id to internal code."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        # Amtrak uses their standard codes as stop_id
        result = map_gtfs_stop_to_station_code("NYP", "New York Penn Station", "AMTRAK")
        assert result == "NY"

        result = map_gtfs_stop_to_station_code("TRE", "Trenton", "AMTRAK")
        assert result == "TR"

    def test_njt_station_mapping_by_name(self):
        """Test mapping NJT GTFS stop by name."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        # NJT uses numeric IDs, so we match by name
        result = map_gtfs_stop_to_station_code(
            "12345", "New York Penn Station", "NJT"
        )
        assert result == "NY"

        result = map_gtfs_stop_to_station_code("67890", "Trenton", "NJT")
        assert result == "TR"

    def test_unmapped_station_returns_none(self):
        """Test that unmapped stations return None."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code(
            "99999", "Unknown Station XYZ", "NJT"
        )
        assert result is None


class TestDownloadIntervalConstant:
    """Test the download interval constant is reasonable."""

    def test_download_interval_is_24_hours(self):
        """Verify download interval is 24 hours as specified."""
        assert GTFS_DOWNLOAD_INTERVAL_HOURS == 24
