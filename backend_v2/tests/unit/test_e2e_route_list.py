"""Static validation of the hardcoded ROUTES table in scripts/e2e-api-test.sh.

The E2E suite probes a hand-maintained list of station pairs. Nothing checked
that list against the station config, so a stale or mistyped code sat in it
until someone ran the suite against a deployment and read the failure — the
route reports "0 trains" either way, whether the backend is broken or the pair
is simply wrong (issue #1795).

These tests parse the real array out of the real script (no copy of it lives
here) and assert the invariants the script's own comments state. They run
offline: every check is against committed config, so they say nothing about
whether an agency currently *serves* a valid pair. That distinction is the
point — #1795 was a valid, correctly-spelled pair that SEPTA had stopped
serving, which only a live probe (the line-coverage sweep) can see.
"""

import re
from pathlib import Path

import pytest

from trackrat.config.route_topology import (
    find_route_for_segment,
    is_directionally_reachable,
    models_directions_separately,
)
from trackrat.config.stations import STATION_NAMES

E2E_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "e2e-api-test.sh"

# Documented at e2e-api-test.sh:334 —
#   "label|from|to|data_source|ml_station|flags|lines"
FIELD_NAMES = ("label", "from", "to", "data_source", "ml_station", "flags", "lines")

# e2e-api-test.sh:336-337. Any other letter is a silent no-op in the script,
# so a typo here would quietly stop skipping a route it meant to skip.
VALID_FLAGS = set("ws")

# e2e-api-test.sh:359-365: sources that can never produce a `planned_work`
# service-alert row. A `lines` value on one of these can never match the
# planned-work index, so it is dead weight that reads as though the row were
# excusable. Only these two sources may carry `lines`.
SOURCES_THAT_CAN_EMIT_PLANNED_WORK = {"NJT", "SUBWAY"}


def _parse_routes() -> list[tuple[int, str]]:
    """Extract the ROUTES=( ... ) entries, with their 1-based line numbers.

    Returns (line_number, raw_entry) so a failure names the line to edit.
    """
    lines = E2E_SCRIPT.read_text().splitlines()

    start = next(
        (i for i, ln in enumerate(lines) if ln.strip() == "ROUTES=("),
        None,
    )
    assert start is not None, f"No 'ROUTES=(' array found in {E2E_SCRIPT}"

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() == ")"),
        None,
    )
    assert end is not None, "ROUTES=( array is not terminated by a ')' line"

    entries: list[tuple[int, str]] = []
    for offset in range(start + 1, end):
        stripped = lines[offset].strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r'"([^"]*)"', stripped)
        assert match, (
            f"{E2E_SCRIPT.name}:{offset + 1}: route entry is not a single "
            f"double-quoted string: {stripped!r}"
        )
        entries.append((offset + 1, match.group(1)))

    assert entries, "Parsed zero route entries — the parser is broken"
    return entries


ROUTES = _parse_routes()


def _fields(entry: str) -> dict[str, str]:
    """Split an entry into named fields, padding the optional trailing ones.

    The script does the same via `IFS='|' read -r ... ` plus `${flags:-}` /
    `${lines:-}` defaults (e2e-api-test.sh:548-550), so a 6-field row is
    equivalent to a 7-field row with an empty `lines`.
    """
    parts = entry.split("|")
    parts += [""] * (len(FIELD_NAMES) - len(parts))
    # strict=False mirrors the shell: `read -r` drops any field past the last
    # named one rather than erroring. An over-long row is caught by
    # test_entry_has_a_well_formed_field_layout instead.
    return dict(zip(FIELD_NAMES, parts, strict=False))


def _ids(entries: list[tuple[int, str]]) -> list[str]:
    return [f"L{line}:{entry.split('|')[0]}" for line, entry in entries]


@pytest.mark.parametrize("line_no,entry", ROUTES, ids=_ids(ROUTES))
def test_entry_has_a_well_formed_field_layout(line_no: int, entry: str) -> None:
    """Every entry splits into 6 or 7 fields with the required ones populated.

    Too few fields silently shifts every later field left — a 5-field row would
    put the ml_station code into `flags`, which the script then ignores.
    """
    parts = entry.split("|")
    assert 6 <= len(parts) <= len(FIELD_NAMES), (
        f"e2e-api-test.sh:{line_no}: expected 6 or 7 '|'-separated fields "
        f"({'|'.join(FIELD_NAMES)}), got {len(parts)}: {entry!r}"
    )

    fields = _fields(entry)
    for required in ("label", "from", "to", "data_source"):
        assert fields[
            required
        ], f"e2e-api-test.sh:{line_no}: field '{required}' is empty in {entry!r}"

    assert fields["from"] != fields["to"], (
        f"e2e-api-test.sh:{line_no}: from and to are the same station "
        f"({fields['from']}) — this pair can never return a departure"
    )


@pytest.mark.parametrize("line_no,entry", ROUTES, ids=_ids(ROUTES))
def test_station_codes_resolve_in_the_station_config(line_no: int, entry: str) -> None:
    """from/to/ml_station must be codes the backend actually knows.

    An unknown code is indistinguishable from an outage in the suite's output:
    the departures query returns an empty board and the route reports
    "0 trains", pointing the reader at the backend rather than at this file.
    """
    fields = _fields(entry)

    for field in ("from", "to", "ml_station"):
        code = fields[field]
        if not code:
            continue  # ml_station is legitimately empty on most rows
        assert code in STATION_NAMES, (
            f"e2e-api-test.sh:{line_no}: {field}='{code}' "
            f"({fields['label']}) is not a known station code. "
            f"Station codes live in trackrat.config.stations; note the SEPTA "
            f"modules are generated by scripts/generate_septa_data.py."
        )


@pytest.mark.parametrize("line_no,entry", ROUTES, ids=_ids(ROUTES))
def test_pair_endpoints_share_a_route(line_no: int, entry: str) -> None:
    """Both endpoints must lie on one common line, reachable in one direction.

    Catches a pair wired across two lines that share no through service — the
    other way a hand-edited entry produces a permanent, misleading "0 trains".

    Every source in the table has topology today (SEPTA's is built dynamically
    from its station config rather than declared as literals), so a missing
    route is treated as a failure rather than skipped: an entry the topology
    cannot place is one the suite cannot meaningfully probe.

    `find_route_for_segment` alone is not sufficient. It resolves via
    `Route.contains_segment`, which tests membership of `_station_set` — the
    *union* of `stations` and `reverse_stations` (route_topology.py:50-54) — so
    it answers "both codes appear somewhere on this line", not "one train runs
    from the first to the second". SEPTA_METRO is the one data source that
    models directions separately, and its trolley curbs carry a distinct code
    per direction, so a pair mixing an outbound curb with an inbound one would
    resolve to a route and still never be served.
    `is_directionally_reachable` closes that: it requires both codes in the
    *same* sequence in the right order, and returns True unconditionally for
    every non-directional source, so it costs nothing elsewhere.
    """
    fields = _fields(entry)
    source, frm, to = fields["data_source"], fields["from"], fields["to"]

    if frm not in STATION_NAMES or to not in STATION_NAMES:
        pytest.skip("covered by test_station_codes_resolve_in_the_station_config")

    route = find_route_for_segment(source, frm, to)
    assert route is not None, (
        f"e2e-api-test.sh:{line_no}: {fields['label']} pairs "
        f"{frm} ({STATION_NAMES[frm]}) with {to} ({STATION_NAMES[to]}) on "
        f"{source}, but route_topology has no single route carrying both. "
        f"A pair with no common line can never return a through departure."
    )

    assert is_directionally_reachable(source, frm, to), (
        f"e2e-api-test.sh:{line_no}: {fields['label']} pairs "
        f"{frm} ({STATION_NAMES[frm]}) with {to} ({STATION_NAMES[to]}) on "
        f"{source}. Both codes lie on {route.name}, but no single direction of "
        f"it runs {frm} -> {to} — they are opposite-direction codes for the "
        f"same corridor. The probe would report 0 trains forever. Use the two "
        f"codes that share one direction's sequence, or swap from/to."
    )


@pytest.mark.parametrize("line_no,entry", ROUTES, ids=_ids(ROUTES))
def test_flags_are_recognized(line_no: int, entry: str) -> None:
    """`flags` may only contain documented letters.

    An unrecognized letter is silently ignored by the script, so a typo'd 'W'
    means a weekday-only route runs — and fails — every weekend.
    """
    flags = _fields(entry)["flags"]
    unknown = set(flags) - VALID_FLAGS
    assert not unknown, (
        f"e2e-api-test.sh:{line_no}: unrecognized flag(s) {sorted(unknown)} in "
        f"flags='{flags}'. Valid flags are 'w' (weekday-only) and 's' "
        f"(schedule-only); anything else is silently ignored by the script."
    )


@pytest.mark.parametrize("line_no,entry", ROUTES, ids=_ids(ROUTES))
def test_lines_only_set_where_planned_work_alerts_exist(
    line_no: int, entry: str
) -> None:
    """`lines` must be empty unless the source can emit a planned_work alert.

    planned_work_note() downgrades an empty board to WARN only when every listed
    line has an active planned-work row (e2e-api-test.sh:240-252). Sources that
    never emit `planned_work` can never satisfy that, so a value here cannot
    excuse anything — it only reads as though the row were excusable. This is
    exactly the trap #1795 hit from the other side: SEPTA is unconditionally
    strict, so a real agency service change read as a backend failure.
    """
    fields = _fields(entry)
    source, lines = fields["data_source"], fields["lines"]

    if not lines:
        return

    assert source in SOURCES_THAT_CAN_EMIT_PLANNED_WORK, (
        f"e2e-api-test.sh:{line_no}: {fields['label']} sets lines='{lines}' on "
        f"{source}, whose alerts are never typed 'planned_work'. The value can "
        f"never match the planned-work index, so it cannot downgrade a 0-train "
        f"board to WARN. Leave it empty (see e2e-api-test.sh:350-365)."
    )


def test_directional_guard_rejects_a_cross_direction_pair() -> None:
    """Pin that the reachability check in test_pair_endpoints_share_a_route bites.

    Every SEPTA_METRO entry in the table today is directionally reachable, so
    that assertion passes whether or not it is doing any work — and a guard that
    can only ever pass is indistinguishable from one that was never added.

    SEPM20876 / SEPM20879 are the two curbs of Baltimore Av & 42nd St on Route
    34 (config/stations/septa_metro.py), the repository's standing example of
    direction-specific codes: the first appears only in the outbound sequence,
    the second only in the inbound one. This asserts the exact gap the check
    closes — `find_route_for_segment` resolves the pair to a route, while
    `is_directionally_reachable` refuses it. If SEPTA's generated config ever
    stops modelling directions separately, this fails loudly rather than
    leaving a silently vacuous assertion behind.
    """
    outbound_curb, inbound_curb = "SEPM20876", "SEPM20879"

    assert models_directions_separately("SEPTA_METRO"), (
        "SEPTA_METRO no longer models directions separately, so the "
        "reachability check in test_pair_endpoints_share_a_route is now a "
        "no-op for every source. Re-derive whether it is still worth keeping."
    )

    route = find_route_for_segment("SEPTA_METRO", outbound_curb, inbound_curb)
    assert route is not None, (
        f"{outbound_curb}/{inbound_curb} no longer resolve to a shared route, "
        f"so this pair no longer demonstrates the gap between union membership "
        f"and directional reachability. Pick another cross-direction pair."
    )

    assert not is_directionally_reachable("SEPTA_METRO", outbound_curb, inbound_curb), (
        f"{outbound_curb} -> {inbound_curb} resolved to {route.name} AND read "
        f"as directionally reachable. They are opposite curbs of one corner, so "
        f"no train runs between them; if this passes, the added assertion "
        f"cannot catch a cross-direction entry."
    )


def test_parser_sees_every_quoted_entry_in_the_array() -> None:
    """Guard the parser itself against silently matching nothing.

    Every other test in this module is parametrized over _parse_routes(), so a
    parser that returned an empty or truncated list would turn the whole file
    green while checking nothing.

    The anchor is the newline-delimited "\\nROUTES=(\\n" rather than a bare
    "ROUTES=(", which is a *substring* of the unrelated `FAILED_ROUTES=()`
    declared ~300 lines earlier — splitting on that matches the wrong array and
    only agrees by luck, exactly the silent lie this guard exists to catch.
    """
    text = E2E_SCRIPT.read_text()
    assert text.count("\nROUTES=(\n") == 1, (
        "Expected exactly one 'ROUTES=(' array declaration on its own line; "
        "the anchor this guard splits on is no longer unambiguous."
    )
    body = text.split("\nROUTES=(\n", 1)[1].split("\n)", 1)[0]
    quoted = re.findall(r'^\s*"([^"]*)"\s*$', body, flags=re.MULTILINE)

    assert len(ROUTES) == len(quoted), (
        f"Parser found {len(ROUTES)} entries but the ROUTES array contains "
        f"{len(quoted)} quoted lines — the parser is dropping entries."
    )
    assert len(ROUTES) >= 40, (
        f"Only {len(ROUTES)} route entries parsed; the array has historically "
        f"held ~49. A sharp drop means the parser or the array shape changed."
    )
