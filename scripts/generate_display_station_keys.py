#!/usr/bin/env python3
"""Regenerate the client mirrors of DISPLAY_STATION_CODES.

One physical station can carry several codes — cross-provider codes for a shared
building, a SEPTA Metro complex's platform codes, SEPTA's per-direction surface
stops. The backend decides which codes are one station in
`config/stations/common.py`; the iOS and web station pickers need the same answer
so they render one row per station instead of one per code.

The map is derived from coordinates and provider data rather than hand-written
(SEPTA alone contributes ~230 entries and regenerates with every feed), so it is
generated into both clients from the backend as the single source of truth.

Both mirrors live inside the clients' existing station-data files rather than in
new ones: `ios/TrackRat/Shared/StationData.swift` is already the iOS mirror, and
a new Swift file would have to be registered by hand in three
`project.pbxproj` targets.

Usage:
    cd backend_v2 && poetry run python ../scripts/generate_display_station_keys.py
    ... --check    # exit 1 if either mirror is stale (no writes)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend_v2" / "src"))

from trackrat.config.stations.common import (  # noqa: E402
    DISPLAY_STATION_CODES,
    STATION_NAMES,
)

WEB_FILE = REPO_ROOT / "webpage_v2" / "src" / "data" / "stations.ts"
IOS_FILE = REPO_ROOT / "ios" / "TrackRat" / "Shared" / "StationData.swift"

BEGIN_MARKER = "DISPLAY_STATION_KEYS GENERATED — do not edit by hand"
END_MARKER = "END DISPLAY_STATION_KEYS GENERATED"


def _non_identity_entries() -> list[tuple[str, str]]:
    """Codes whose display key is some *other* code, sorted for stable diffs.

    Codes that represent their own station are omitted: both clients fall back
    to the code itself, so listing them would only pad the table.
    """
    return sorted(
        (code, key) for code, key in DISPLAY_STATION_CODES.items() if code != key
    )


def _grouped_by_key() -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = {}
    for code, key in _non_identity_entries():
        groups.setdefault(key, []).append(code)
    return sorted(groups.items())


def render_typescript() -> str:
    lines = [
        f"// {BEGIN_MARKER}",
        "// Regenerate: cd backend_v2 && poetry run python \\",
        "//   ../scripts/generate_display_station_keys.py",
        "//",
        "// Maps a station code to the code representing its physical station, for",
        "// codes that are not their own representative. Search results are deduped",
        "// by this key so one station occupies one row (see displayStationKey).",
        "export const DISPLAY_STATION_KEYS: Readonly<Record<string, string>> = {",
    ]
    for key, codes in _grouped_by_key():
        lines.append(f"  // {STATION_NAMES.get(key, key)} ({key})")
        for code in codes:
            lines.append(f"  {code}: '{key}',")
    lines.append("};")
    lines.append(f"// {END_MARKER}")
    return "\n".join(lines)


def render_swift() -> str:
    lines = [
        f"    // {BEGIN_MARKER}",
        "    // Regenerate: cd backend_v2 && poetry run python \\",
        "    //   ../scripts/generate_display_station_keys.py",
        "    //",
        "    // Maps a station code to the code representing its physical station,",
        "    // for codes that are not their own representative. Search results are",
        "    // deduped by this key so one station occupies one row.",
        "    static let displayStationKeys: [String: String] = [",
    ]
    for key, codes in _grouped_by_key():
        lines.append(f"        // {STATION_NAMES.get(key, key)} ({key})")
        for code in codes:
            lines.append(f'        "{code}": "{key}",')
    lines.append("    ]")
    lines.append(f"    // {END_MARKER}")
    return "\n".join(lines)


def replace_block(path: Path, rendered: str) -> str:
    """Swap the generated region in `path` for `rendered`, returning the result."""
    text = path.read_text()
    begin_index = text.find(BEGIN_MARKER)
    end_index = text.find(END_MARKER)
    if begin_index == -1 or end_index == -1:
        raise SystemExit(
            f"{path}: could not find the generated block markers. Expected a "
            f"region delimited by {BEGIN_MARKER!r} and {END_MARKER!r}."
        )
    # Expand to whole lines so the comment prefix ("// " / "    // ") is replaced too.
    block_start = text.rfind("\n", 0, begin_index) + 1
    block_end = text.find("\n", end_index)
    if block_end == -1:
        block_end = len(text)
    return text[:block_start] + rendered + text[block_end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if a mirror is stale instead of rewriting it",
    )
    args = parser.parse_args()

    targets = [(WEB_FILE, render_typescript()), (IOS_FILE, render_swift())]
    stale: list[Path] = []
    for path, rendered in targets:
        updated = replace_block(path, rendered)
        if updated == path.read_text():
            continue
        if args.check:
            stale.append(path)
        else:
            path.write_text(updated)
            print(f"updated {path.relative_to(REPO_ROOT)}")

    if stale:
        print(
            "Stale display-station-key mirrors:\n  "
            + "\n  ".join(str(p.relative_to(REPO_ROOT)) for p in stale)
            + "\nRegenerate with: cd backend_v2 && poetry run python "
            "../scripts/generate_display_station_keys.py",
            file=sys.stderr,
        )
        return 1

    if not args.check:
        print(f"{len(_non_identity_entries())} entries written to both mirrors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
