"""Static validation of the hardcoded ROUTES table in scripts/e2e-api-test.sh,
plus the planned-work excuse for transfer trip searches (end of file).

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

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from trackrat.config.route_topology import (
    find_route_for_segment,
    get_routes_for_data_source,
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


# ── Planned-work excuses for transfer trip searches (issue #1884) ───────────
#
# A transfer itinerary is excused only when one of its required legs has every
# line that can serve it suspended. The pieces live in the script as a Python
# heredoc (the alert indexer) and two shell functions; these tests run the real
# text of each, extracted from the script, against fixture inputs.


def _indexer_source() -> str:
    """The alert-indexer heredoc, verbatim."""
    text = E2E_SCRIPT.read_text()
    match = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY\n", text, flags=re.DOTALL)
    assert match, "No <<'PY' heredoc found in the script — the indexer moved"
    return match.group(1)


def _shell_function(name: str) -> str:
    """A top-level shell function definition, from `name() {` to its `}`."""
    match = re.search(
        rf"^{name}\(\) \{{\n.*?^\}}$", E2E_SCRIPT.read_text(), re.DOTALL | re.MULTILINE
    )
    assert match, f"No top-level '{name}() {{' function in {E2E_SCRIPT.name}"
    return match.group(0)


def _run_indexer(tmp_path: Path, alerts: list[dict]) -> dict[tuple[str, str], str]:
    """Run the indexer on `alerts`; return {(route_id, headline): suspended}."""
    alerts_file, tsv = tmp_path / "alerts.json", tmp_path / "planned_work.tsv"
    alerts_file.write_text(json.dumps({"alerts": alerts}))
    script = tmp_path / "indexer.py"
    script.write_text(_indexer_source())
    subprocess.run(
        [sys.executable, "-I", str(script), str(alerts_file), str(tsv)], check=True
    )
    rows = [line.split("\t") for line in tsv.read_text().splitlines()]
    print("indexed rows:", *rows, sep="\n  ")
    assert all(len(r) == 4 for r in rows), f"expected 4 TSV columns: {rows}"
    return {(route, headline): suspended for _, route, headline, suspended in rows}


def _subway_alert(header_text: str, *routes: str) -> dict:
    # No active_periods: the indexer treats the alert as in force now.
    return {
        "alert_type": "planned_work",
        "data_source": "SUBWAY",
        "header_text": header_text,
        "affected_route_ids": list(routes),
    }


# Two clauses, each suspending a different line; the [6] one starts past the
# 120-character headline cut, so it is only visible in the full header_text.
TWO_LINE_SUSPENSION = (
    "No [4] between Grand Central-42 St, Manhattan and Utica Av/New Lots Av, "
    "Brooklyn. Take the [5] or [2] instead for service along the route. "
    "No [6] between Grand Central-42 St and Brooklyn Bridge-City Hall"
)


@pytest.mark.parametrize(
    "header_text,route,expected",
    [
        # Suspensions, in every wording seen on production 2026-10-11.
        ("No [L] between Lorimer St, Brooklyn and 8 Av, Manhattan", "L", "1"),
        (
            "In Upper Manhattan, no [1] between 137 St-City College and "
            "168 St-Washington Hts",
            "1",
            "1",
        ),
        ("Overnight [3] is suspended", "3", "1"),
        # One station closed, not the line.
        ("In the Bronx, no [1] at Van Cortlandt Park-242 St", "1", "0"),
        # Ordinary planned work: never a suspension.
        ("In the Bronx, Woodlawn-bound [4] skips Burnside Av", "4", "0"),
        (
            "In Manhattan, [4] runs local in both directions between 125 St "
            "and Grand Central-42 St",
            "4",
            "0",
        ),
        ("[5] runs every 20 minutes and local in both directions", "5", "0"),
        # Another line's suspension clause must not mark this row.
        ("No [4] between Grand Central-42 St and Utica Av. [5] runs local", "5", "0"),
        # Known limit: bracket text that differs from the route id ([SIR] for
        # SI) is not recognized. A miss keeps the check at FAIL, never hides one.
        ("No [SIR] between St George and Tottenville", "SI", "0"),
    ],
)
def test_indexer_marks_only_suspensions_of_the_rows_own_line(
    tmp_path: Path, header_text: str, route: str, expected: str
) -> None:
    index = _run_indexer(tmp_path, [_subway_alert(header_text, route)])
    assert index == {(route, header_text[:120]): expected}, (
        f"route {route!r} in {header_text!r}: expected suspended={expected}, "
        f"indexed {index}"
    )


def test_indexer_classifies_each_line_of_a_multi_clause_alert(tmp_path: Path) -> None:
    """Both lines of a two-clause alert are suspended, including the late one."""
    assert TWO_LINE_SUSPENSION.index("No [6]") > 120, "fixture no longer tests the cut"

    index = _run_indexer(tmp_path, [_subway_alert(TWO_LINE_SUSPENSION, "4", "6")])

    headline = TWO_LINE_SUSPENSION[:120]
    assert index == {("4", headline): "1", ("6", headline): "1"}, (
        "The [6] clause sits past the 120-char headline; classifying the "
        f"truncated text would miss it. Indexed: {index}"
    )


def _legs_note(tmp_path: Path, rows: list[tuple[str, str, str, str]], *args: str):
    """Call a note function from the script with a fixture planned_work.tsv.

    `args` is the function name followed by its arguments. Returns (exit code,
    stdout).
    """
    (tmp_path / "planned_work.tsv").write_text(
        "".join("\t".join(r) + "\n" for r in rows)
    )
    njt_re = re.search(r"^NJT_CLOSURE_RE=.*$", E2E_SCRIPT.read_text(), re.MULTILINE)
    assert njt_re, "NJT_CLOSURE_RE assignment not found"
    program = "\n".join(
        [
            f"TMPDIR='{tmp_path}'",
            njt_re.group(0),
            _shell_function("planned_work_note"),
            _shell_function("required_legs_note"),
            '"$@"',
        ]
    )
    result = subprocess.run(
        ["bash", "-c", program, "bash", *args], capture_output=True, text=True
    )
    print(f"{' '.join(args)} -> rc={result.returncode} out={result.stdout!r}")
    assert not result.stderr, f"shell error: {result.stderr}"
    return result.returncode, result.stdout.strip()


L_SUSPENDED = ("SUBWAY", "L", "No [L] between Lorimer St and 8 Av", "1")
Q_SUSPENDED = ("SUBWAY", "Q", "No [Q] between Prospect Park and Coney Island", "1")
FOUR_LOCAL = ("SUBWAY", "4", "[4] runs local between 125 St and Grand Central", "0")
FIVE_LOCAL = ("SUBWAY", "5", "[5] runs local between 125 St and Grand Central", "0")


def test_required_legs_excused_when_one_leg_is_fully_suspended(tmp_path: Path) -> None:
    rc, out = _legs_note(
        tmp_path, [FOUR_LOCAL, L_SUSPENDED], "required_legs_note", "SUBWAY", "L;4,5"
    )
    assert (rc, out) == (0, L_SUSPENDED[2])


def test_required_legs_not_excused_while_another_line_serves_the_leg(
    tmp_path: Path,
) -> None:
    """Coney Island is reached by D, F, N and Q; a Q suspension leaves three."""
    rc, out = _legs_note(
        tmp_path, [Q_SUSPENDED], "required_legs_note", "SUBWAY", "A;D,F,N,Q"
    )
    assert (rc, out) == (1, "")


def test_required_legs_ignore_planned_work_that_is_not_a_suspension(
    tmp_path: Path,
) -> None:
    """Every line of the 4/5 leg has planned work, but none is suspended."""
    rc, out = _legs_note(
        tmp_path, [FOUR_LOCAL, FIVE_LOCAL], "required_legs_note", "SUBWAY", "L;4,5"
    )
    assert (rc, out) == (1, "")


def test_required_legs_match_only_the_given_source(tmp_path: Path) -> None:
    rc, _ = _legs_note(tmp_path, [L_SUSPENDED], "required_legs_note", "NJT", "L")
    assert rc == 1


def test_required_legs_empty_never_excuses(tmp_path: Path) -> None:
    rc, _ = _legs_note(tmp_path, [L_SUSPENDED], "required_legs_note", "SUBWAY", "")
    assert rc == 1


def test_lines_rule_still_accepts_any_planned_work(tmp_path: Path) -> None:
    """The ROUTES `lines` rule (issue #1771) is unchanged by the suspension mode."""
    rc, out = _legs_note(
        tmp_path, [FOUR_LOCAL, FIVE_LOCAL], "planned_work_note", "SUBWAY", "4,5"
    )
    assert (rc, out) == (0, FOUR_LOCAL[2])


def _trip_bidi_calls() -> list[tuple[int, list[str]]]:
    """Every `trip_bidi "…" …` call, as (line number, quoted args).

    Includes indented calls: a pair whose leg groups vary by day is called from
    both branches of an `if`, and each branch must be checked.
    """
    calls = []
    for no, line in enumerate(E2E_SCRIPT.read_text().splitlines(), start=1):
        if line.lstrip().startswith("trip_bidi "):
            calls.append((no, re.findall(r'"([^"]*)"', line)))
    assert len(calls) >= 20, f"Only {len(calls)} trip_bidi calls parsed"
    return calls


TRIP_CALLS_WITH_LEGS = [(no, args) for no, args in _trip_bidi_calls() if len(args) > 7]
SUBWAY_LINE_CODES = {
    code for route in get_routes_for_data_source("SUBWAY") for code in route.line_codes
}
LEG_GROUPS_RE = re.compile(r"[^;,]+(,[^;,]+)*(;[^;,]+(,[^;,]+)*)*")


def test_every_subway_transfer_pair_has_leg_groups() -> None:
    """Without leg groups, a weekend suspension fails the deploy gate (#1884)."""
    missing = [
        f"e2e-api-test.sh:{no}: {args[0]}"
        for no, args in _trip_bidi_calls()
        if args[0].startswith("SUBWAY")
        and args[3] == "transfer"
        and (len(args) < 8 or not args[7])
    ]
    assert not missing, "Subway transfer pairs without leg groups:\n" + "\n".join(
        missing
    )


@pytest.mark.parametrize(
    "line_no,args",
    TRIP_CALLS_WITH_LEGS,
    ids=[f"L{no}:{args[0]}" for no, args in TRIP_CALLS_WITH_LEGS],
)
def test_leg_groups_are_well_formed_subway_line_codes(
    line_no: int, args: list[str]
) -> None:
    label, source, legs = args[0], args[5], args[7]
    assert source == "SUBWAY", (
        f"e2e-api-test.sh:{line_no}: {label} sets leg groups with source "
        f"{source!r}; only SUBWAY alerts carry the `No [X] between` wording "
        f"the suspension classifier recognizes"
    )
    assert LEG_GROUPS_RE.fullmatch(legs), (
        f"e2e-api-test.sh:{line_no}: {label} legs={legs!r} is not "
        f"';'-separated groups of ','-separated line codes"
    )
    codes = set(re.split("[;,]", legs))
    unknown = codes - SUBWAY_LINE_CODES
    assert not unknown, (
        f"e2e-api-test.sh:{line_no}: {label} legs={legs!r} names "
        f"{sorted(unknown)}, which are not SUBWAY line codes in route_topology; "
        f"no alert row can ever match them, so that leg can never be excused"
    )
