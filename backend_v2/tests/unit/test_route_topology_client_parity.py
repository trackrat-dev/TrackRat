"""The three hand-maintained copies of the route topology must stay consistent.

The station order lives in three places — `config/route_topology.py`,
`ios/TrackRat/Shared/RouteTopology.swift` and `webpage_v2/src/data/routeTopology.ts`.
The TS file is labelled "Auto-generated from backend route_topology.py", but no
generator exists anywhere in `scripts/`: both client tables are edited by hand,
so nothing makes them agree and nothing notices when they don't.

**What these tests do and do not catch.** They would *not* have caught issue
#1660 on their own: all three copies carried the same wrong order, so they
agreed with each other. Catching that is the geographic zig-zag test's job
(`test_port_jervis_order_is_not_improved_by_swapping_neighbours`). What these
catch is the complementary risk, and the one #1660's fix creates: an ordering
corrected in one copy and forgotten in another. That fix touched all three by
hand, and a partial revert would restore the disconnected map on one client
only — the hardest version to notice.

**The invariant is subsequence, not equality.** The clients deliberately carry
fewer stations: the backend prefixes `njt-port-jervis` and `njt-gladstone` with
the Main Line trunk so skip-stop segments can be expanded to canonical pairs,
and the clients sample only major stops on Amtrak long-distance routes. So each
client list must appear *in order* within the backend's — which still fails on a
transposition like #1660's, while permitting the sampling. Reversal is allowed
too: iOS lists `amtrak-surfliner` and `amtrak-cascades` southbound where the
backend runs northbound, which is a direction convention, not a defect.
"""

import re
from fnmatch import fnmatch
from pathlib import Path

import pytest

from trackrat.config.route_topology import ALL_ROUTES

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SWIFT_TOPOLOGY = _REPO_ROOT / "ios/TrackRat/Shared/RouteTopology.swift"
_TS_TOPOLOGY = _REPO_ROOT / "webpage_v2/src/data/routeTopology.ts"

# This module lives in backend_v2 but reads the two client files above, so it
# only runs when CI decides a change touched the backend. See
# TestTheParityCheckRunsWhenAClientTableChanges.
_CI_WORKFLOW = _REPO_ROOT / ".github/workflows/ci-cd-v2.yml"
_SWIFT_TOPOLOGY_REPO_PATH = "ios/TrackRat/Shared/RouteTopology.swift"
_TS_TOPOLOGY_REPO_PATH = "webpage_v2/src/data/routeTopology.ts"

# Both clients quote every station code, so one expression reads either file.
_CODES = re.compile(r'"([^"]*)"')


def _parse_swift(source: str) -> dict[str, tuple[str, ...]]:
    """Map route id -> station codes from RouteTopology.swift.

    Matches `id: "..."` followed by the next `stationCodes: [...]`, which is
    the shape every `RouteLine(...)` literal in that file uses.
    """
    pattern = re.compile(
        r'id:\s*"(?P<id>[^"]+)".*?stationCodes:\s*\[(?P<codes>[^\]]*)\]',
        re.DOTALL,
    )
    return {
        m.group("id"): tuple(_CODES.findall(m.group("codes")))
        for m in pattern.finditer(source)
    }


def _parse_typescript(source: str) -> dict[str, tuple[str, ...]]:
    """Map route id -> station codes from routeTopology.ts.

    Route ids are single-quoted there and station codes double-quoted, so the
    two stay unambiguous even though each record sits on one line.
    """
    pattern = re.compile(
        r"id:\s*'(?P<id>[^']+)'.*?stations:\s*\[(?P<codes>[^\]]*)\]",
        re.DOTALL,
    )
    return {
        m.group("id"): tuple(_CODES.findall(m.group("codes")))
        for m in pattern.finditer(source)
    }


def _trigger_path_blocks(source: str) -> list[tuple[str, ...]]:
    """Every `paths:` filter in a workflow, in file order.

    A small parser rather than PyYAML, which the backend does not depend on —
    and which is not worth adding for one assertion. Comments and blank lines
    inside a block are skipped; any other key ends it.
    """
    blocks: list[tuple[str, ...]] = []
    globs: list[str] | None = None
    for line in source.splitlines():
        stripped = line.strip()
        if stripped == "paths:":
            if globs is not None:
                blocks.append(tuple(globs))
            globs = []
            continue
        if globs is None:
            continue
        item = re.match(r"^-\s*'(?P<glob>[^']+)'$", stripped)
        if item:
            globs.append(item.group("glob"))
        elif stripped and not stripped.startswith("#"):
            blocks.append(tuple(globs))
            globs = None
    if globs is not None:
        blocks.append(tuple(globs))
    return blocks


def _is_covered(globs: tuple[str, ...], repo_path: str) -> bool:
    """True if a change to `repo_path` matches any of a trigger's globs."""
    return any(fnmatch(repo_path, glob) for glob in globs)


def _is_ordered_subset(client: tuple[str, ...], backend: tuple[str, ...]) -> bool:
    """True if every client station appears, in order, within `backend`."""
    remaining = iter(backend)
    return all(code in remaining for code in client)


def _agrees_with_backend(client: tuple[str, ...], backend: tuple[str, ...]) -> bool:
    """Subsequence in either direction — see the module docstring on reversal."""
    return _is_ordered_subset(client, backend) or _is_ordered_subset(
        client, tuple(reversed(backend))
    )


@pytest.fixture(scope="module")
def backend_routes() -> dict[str, tuple[str, ...]]:
    return {route.id: tuple(route.stations) for route in ALL_ROUTES}


@pytest.fixture(scope="module")
def swift_routes() -> dict[str, tuple[str, ...]]:
    return _parse_swift(_SWIFT_TOPOLOGY.read_text())


@pytest.fixture(scope="module")
def typescript_routes() -> dict[str, tuple[str, ...]]:
    return _parse_typescript(_TS_TOPOLOGY.read_text())


@pytest.fixture(scope="module")
def ci_path_blocks() -> list[tuple[str, ...]]:
    return _trigger_path_blocks(_CI_WORKFLOW.read_text())


class TestParsersActuallyReadTheClientFiles:
    """A silently-empty parser would make every parity test below vacuous.

    This is the failure mode that matters most here: if a client file is
    reformatted so the regex stops matching, the parity tests would pass by
    having nothing to compare. These assert the parsers see real content.
    """

    def test_swift_table_is_parsed(self, swift_routes):
        assert len(swift_routes) > 100
        assert swift_routes["njt-nec"][0] == "NY"

    def test_typescript_table_is_parsed(self, typescript_routes):
        assert len(typescript_routes) > 100
        assert typescript_routes["njt-nec"][0] == "NY"

    def test_both_clients_are_compared_against_many_shared_routes(
        self, backend_routes, swift_routes, typescript_routes
    ):
        """Guards the `route_id in backend_routes` filter from emptying out."""
        assert len(set(swift_routes) & set(backend_routes)) > 100
        assert len(set(typescript_routes) & set(backend_routes)) > 100

    def test_parsers_reject_a_file_with_no_route_literals(self):
        assert _parse_swift("// nothing here") == {}
        assert _parse_typescript("// nothing here") == {}


class TestOrderedSubsetHelper:
    """The invariant itself must reject a transposition, or it proves nothing."""

    def test_accepts_a_sampled_subset(self):
        assert _is_ordered_subset(("A", "C", "E"), ("A", "B", "C", "D", "E"))

    def test_accepts_the_full_sequence(self):
        assert _is_ordered_subset(("A", "B", "C"), ("A", "B", "C"))

    def test_rejects_a_transposition(self):
        """#1660's shape: right stations, wrong order."""
        assert not _is_ordered_subset(("A", "C", "B"), ("A", "B", "C"))

    def test_rejects_an_unknown_station(self):
        assert not _is_ordered_subset(("A", "Z"), ("A", "B", "C"))

    def test_reversal_is_only_accepted_by_the_bidirectional_check(self):
        assert not _is_ordered_subset(("C", "B", "A"), ("A", "B", "C"))
        assert _agrees_with_backend(("C", "B", "A"), ("A", "B", "C"))


class TestTheParityCheckRunsWhenAClientTableChanges:
    """A parity test CI never runs is worth nothing.

    These tests live in `backend_v2`, so `ci-cd-v2.yml`'s path filter decides
    whether they execute. The web table sits under `webpage_v2/**` and was
    always covered, but the Swift table is under `ios/**`: before this was
    pinned, an iOS-only topology edit ran `ios-ci.yml` alone — Xcode only —
    and the one-client drift these tests exist to catch merged unnoticed.
    """

    def test_both_triggers_are_parsed(self, ci_path_blocks):
        """Guards against the parser silently finding nothing."""
        assert len(ci_path_blocks) == 2, ci_path_blocks
        assert all("backend_v2/**" in globs for globs in ci_path_blocks)

    def test_swift_topology_changes_trigger_this_suite(self, ci_path_blocks):
        for globs in ci_path_blocks:
            assert _is_covered(globs, _SWIFT_TOPOLOGY_REPO_PATH), (
                "ci-cd-v2.yml no longer runs on the Swift topology file, so "
                "iOS-only drift would merge unchecked: " + repr(globs)
            )

    def test_typescript_topology_changes_trigger_this_suite(self, ci_path_blocks):
        for globs in ci_path_blocks:
            assert _is_covered(globs, _TS_TOPOLOGY_REPO_PATH), repr(globs)

    def test_the_ios_trigger_stays_narrow(self, ci_path_blocks):
        """Only the topology file — not all of `ios/**`.

        Backend/terraform/docker/web jobs have nothing to say about an Xcode
        change, which is why `ios-ci.yml` exists as a separate workflow.
        """
        for globs in ci_path_blocks:
            assert not _is_covered(globs, "ios/TrackRat/App/ContentView.swift")

    def test_the_coverage_helpers_discriminate(self):
        """Otherwise the assertions above could pass vacuously."""
        assert _is_covered(("ios/**",), _SWIFT_TOPOLOGY_REPO_PATH)
        assert not _is_covered(("backend_v2/**",), _SWIFT_TOPOLOGY_REPO_PATH)
        assert not _is_covered((), _SWIFT_TOPOLOGY_REPO_PATH)
        assert _trigger_path_blocks("on:\n  push:\n    branches: [main]\n") == []


class TestClientTopologiesAgreeWithTheBackend:
    def test_swift_station_orders_agree(self, backend_routes, swift_routes):
        """Every route iOS shares with the backend must keep its ordering."""
        mismatches = {
            route_id: {"backend": backend_routes[route_id], "swift": stations}
            for route_id, stations in swift_routes.items()
            if route_id in backend_routes
            and not _agrees_with_backend(stations, backend_routes[route_id])
        }
        assert not mismatches, f"iOS topology drifted from the backend: {mismatches}"

    def test_typescript_station_orders_agree(self, backend_routes, typescript_routes):
        """Same for the web table, which drives RouteMap.tsx."""
        mismatches = {
            route_id: {"backend": backend_routes[route_id], "web": stations}
            for route_id, stations in typescript_routes.items()
            if route_id in backend_routes
            and not _agrees_with_backend(stations, backend_routes[route_id])
        }
        assert not mismatches, f"web topology drifted from the backend: {mismatches}"

    def test_web_route_ids_all_exist_in_the_backend(
        self, backend_routes, typescript_routes
    ):
        """A client route id the backend doesn't know is unreachable.

        Asserted for the web table only. iOS currently carries 26 SEPTA ids in
        a different convention (`SEPTA-AIR` vs `septa-rr-air`); that is a known
        drift already being corrected on the branch for #1631, and pinning it
        here would collide with that change.
        """
        assert not set(typescript_routes) - set(backend_routes)

    def test_port_jervis_is_consistent_across_all_three(
        self, backend_routes, swift_routes, typescript_routes
    ):
        """The #1660 route itself, pinned in all three places at once.

        Spelled out rather than derived, so a partial revert of the fix names
        the file it happened in.
        """
        expected = ("SF", "XG", "TC", "RM", "CW", "CB", "MD", "OS", "PO")
        assert backend_routes["njt-port-jervis"][-9:] == expected
        assert swift_routes["njt-port-jervis"] == expected
        assert typescript_routes["njt-port-jervis"] == expected
