"""
System-level metrics: disk usage, memory, and CPU load.

Uses stdlib and /proc filesystem — no external dependencies.
All functions degrade gracefully if /proc is unavailable.
"""

import shutil
from pathlib import Path
from typing import Any


def get_disk_usage(path: str = "/") -> dict[str, Any]:
    """Get disk usage for the given mount point.

    Returns dict with total_gb, used_gb, free_gb, usage_percent.
    """
    try:
        usage = shutil.disk_usage(path)
        total_gb = round(usage.total / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        usage_percent = (
            round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0
        )
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "usage_percent": usage_percent,
        }
    except OSError:
        return {}


def get_memory_usage() -> dict[str, Any]:
    """Get memory usage from /proc/meminfo.

    Returns dict with total_gb, available_gb, usage_percent.
    """
    try:
        meminfo: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                # Values in /proc/meminfo are in kB
                meminfo[key] = int(parts[1])

        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", 0)
        if total_kb == 0:
            return {}

        total_gb = round(total_kb / (1024**2), 2)
        available_gb = round(available_kb / (1024**2), 2)
        used_gb = round((total_kb - available_kb) / (1024**2), 2)
        usage_percent = round((total_kb - available_kb) / total_kb * 100, 1)
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": available_gb,
            "usage_percent": usage_percent,
        }
    except (OSError, ValueError, KeyError):
        return {}


def get_cpu_load() -> dict[str, Any]:
    """Get CPU load averages from /proc/loadavg.

    Returns dict with load_1m, load_5m, load_15m.
    """
    try:
        parts = Path("/proc/loadavg").read_text().split()
        return {
            "load_1m": float(parts[0]),
            "load_5m": float(parts[1]),
            "load_15m": float(parts[2]),
        }
    except (OSError, ValueError, IndexError):
        return {}


def get_system_stats() -> dict[str, Any]:
    """Collect all system-level metrics.

    Returns a dict with disk, memory, and cpu sections.
    Only includes sections that could be read successfully.
    """
    stats: dict[str, Any] = {}

    disk = get_disk_usage("/")
    if disk:
        stats["disk"] = disk

    memory = get_memory_usage()
    if memory:
        stats["memory"] = memory

    cpu = get_cpu_load()
    if cpu:
        stats["cpu"] = cpu

    return stats
