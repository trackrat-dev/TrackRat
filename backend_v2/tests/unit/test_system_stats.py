"""Tests for system_stats utility module.

Validates disk, memory, and CPU metric collection from stdlib/procfs.
Tests both real system reads and graceful degradation when sources are unavailable.
"""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from trackrat.utils.system_stats import (
    get_cpu_load,
    get_disk_usage,
    get_memory_usage,
    get_system_stats,
)


class TestGetDiskUsage:
    """Tests for get_disk_usage()."""

    def test_returns_real_disk_stats(self) -> None:
        """Should return real disk usage for root filesystem."""
        result = get_disk_usage("/")
        assert result, "Expected non-empty dict from real filesystem"
        assert "total_gb" in result
        assert "used_gb" in result
        assert "free_gb" in result
        assert "usage_percent" in result

        # Sanity: total should be positive, percent in range
        assert (
            result["total_gb"] > 0
        ), f"total_gb should be positive, got {result['total_gb']}"
        assert (
            0 <= result["usage_percent"] <= 100
        ), f"usage_percent out of range: {result['usage_percent']}"
        # used + free <= total (reserved blocks may account for the difference)
        assert result["used_gb"] + result["free_gb"] <= result["total_gb"] + 0.1, (
            f"used ({result['used_gb']}) + free ({result['free_gb']}) > "
            f"total ({result['total_gb']})"
        )

    def test_matches_shutil_directly(self) -> None:
        """Values should match shutil.disk_usage output."""
        result = get_disk_usage("/")
        raw = shutil.disk_usage("/")
        expected_pct = round(raw.used / raw.total * 100, 1)
        assert result["usage_percent"] == expected_pct

    def test_invalid_path_returns_empty(self) -> None:
        """Should return empty dict for non-existent path."""
        result = get_disk_usage("/nonexistent/path/that/does/not/exist")
        assert result == {}

    def test_oserror_returns_empty(self) -> None:
        """Should return empty dict when shutil raises OSError."""
        with patch(
            "trackrat.utils.system_stats.shutil.disk_usage", side_effect=OSError("boom")
        ):
            result = get_disk_usage("/")
        assert result == {}


class TestGetMemoryUsage:
    """Tests for get_memory_usage()."""

    def test_returns_real_memory_stats(self) -> None:
        """Should return real memory stats from /proc/meminfo if available."""
        result = get_memory_usage()
        if not Path("/proc/meminfo").exists():
            pytest.skip("/proc/meminfo not available on this platform")

        assert result, "Expected non-empty dict from /proc/meminfo"
        assert "total_gb" in result
        assert "used_gb" in result
        assert "available_gb" in result
        assert "usage_percent" in result

        assert (
            result["total_gb"] > 0
        ), f"total_gb should be positive, got {result['total_gb']}"
        assert (
            0 <= result["usage_percent"] <= 100
        ), f"usage_percent out of range: {result['usage_percent']}"

    def test_missing_proc_returns_empty(self) -> None:
        """Should return empty dict when /proc/meminfo doesn't exist."""
        with patch.object(Path, "read_text", side_effect=OSError("no /proc")):
            result = get_memory_usage()
        assert result == {}

    def test_malformed_meminfo_returns_empty(self) -> None:
        """Should return empty dict when meminfo content is garbage."""
        with patch.object(Path, "read_text", return_value="not valid meminfo data\n"):
            result = get_memory_usage()
        # MemTotal won't be found, total_kb=0, returns empty
        assert result == {}

    def test_parses_known_meminfo_format(self) -> None:
        """Should correctly parse a known /proc/meminfo snippet."""
        fake_meminfo = (
            "MemTotal:        8000000 kB\n"
            "MemFree:         1000000 kB\n"
            "MemAvailable:    3000000 kB\n"
            "Buffers:          500000 kB\n"
        )
        with patch.object(Path, "read_text", return_value=fake_meminfo):
            result = get_memory_usage()

        assert result["total_gb"] == round(8000000 / (1024**2), 2)
        assert result["available_gb"] == round(3000000 / (1024**2), 2)
        assert result["used_gb"] == round(5000000 / (1024**2), 2)
        assert result["usage_percent"] == round(5000000 / 8000000 * 100, 1)


class TestGetCpuLoad:
    """Tests for get_cpu_load()."""

    def test_returns_real_cpu_load(self) -> None:
        """Should return real load averages from /proc/loadavg if available."""
        result = get_cpu_load()
        if not Path("/proc/loadavg").exists():
            pytest.skip("/proc/loadavg not available on this platform")

        assert result, "Expected non-empty dict from /proc/loadavg"
        assert "load_1m" in result
        assert "load_5m" in result
        assert "load_15m" in result

        # Load averages should be non-negative
        assert result["load_1m"] >= 0
        assert result["load_5m"] >= 0
        assert result["load_15m"] >= 0

    def test_missing_proc_returns_empty(self) -> None:
        """Should return empty dict when /proc/loadavg doesn't exist."""
        with patch.object(Path, "read_text", side_effect=OSError("no /proc")):
            result = get_cpu_load()
        assert result == {}

    def test_parses_known_loadavg_format(self) -> None:
        """Should correctly parse a known /proc/loadavg line."""
        with patch.object(
            Path, "read_text", return_value="1.23 4.56 7.89 2/300 12345\n"
        ):
            result = get_cpu_load()

        assert result["load_1m"] == 1.23
        assert result["load_5m"] == 4.56
        assert result["load_15m"] == 7.89


class TestGetSystemStats:
    """Tests for the aggregate get_system_stats()."""

    def test_returns_all_sections_on_linux(self) -> None:
        """On Linux, should return disk, memory, and cpu sections."""
        result = get_system_stats()
        # Disk should always work (shutil is cross-platform)
        assert (
            "disk" in result
        ), f"Missing disk section. Got keys: {list(result.keys())}"

        if Path("/proc/meminfo").exists():
            assert "memory" in result, "Missing memory section on Linux"
        if Path("/proc/loadavg").exists():
            assert "cpu" in result, "Missing cpu section on Linux"

    def test_omits_empty_sections(self) -> None:
        """Should not include sections that returned empty dicts."""
        with (
            patch("trackrat.utils.system_stats.get_disk_usage", return_value={}),
            patch("trackrat.utils.system_stats.get_memory_usage", return_value={}),
            patch("trackrat.utils.system_stats.get_cpu_load", return_value={}),
        ):
            result = get_system_stats()

        assert result == {}, f"Expected empty dict when all sources fail, got {result}"

    def test_partial_availability(self) -> None:
        """Should include only available sections."""
        with (
            patch("trackrat.utils.system_stats.get_memory_usage", return_value={}),
            patch("trackrat.utils.system_stats.get_cpu_load", return_value={}),
        ):
            result = get_system_stats()

        # Disk should still be present (real shutil)
        assert "disk" in result
        assert "memory" not in result
        assert "cpu" not in result
