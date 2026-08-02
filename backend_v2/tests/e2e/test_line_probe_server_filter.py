"""End-to-end tests for the line-coverage probe against the real departures API.

Issue #1629: ``_probe_line_departures`` used to fetch up to 50 *unscoped*
departures and filter by line in Python afterwards. At a busy shared terminal
the sibling lines fill every row, so the sweep reported a perfectly healthy line
as dark. The fix sends the endpoint's ``lines`` parameter, which
``DepartureService`` applies *before* the result limit.

That guarantee lives in the server, not in the probe, so these tests drive the
probe through the real FastAPI app and a real database: the request is built by
``fetch_trackrat_departures``, parsed by ``_parse_trackrat_departures``, and
answered by the actual endpoint. Nothing about the departures path is
substituted — ``starlette``'s ``TestClient`` is an ``httpx.Client``, so the
script's own HTTP code runs unmodified against the ASGI app.
"""

import os
import sys
from datetime import timedelta
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))
gtv = import_module("ground-truth-validate")

# TestClient answers any absolute URL through its ASGI transport, so this only
# has to be a well-formed base for the script's own URL construction.
BASE_URL = "http://testserver"

# NJT Main and Bergen County both run Hoboken -> Suffern; that shared segment is
# exactly the shape that made a running line look dark.
ORIGIN = "HB"
TERMINAL = "SF"
STATIONS = [ORIGIN, TERMINAL]
MAIN = "ML"
BERGEN = "NC"

# fetch_trackrat_departures requests limit=50; 60 siblings guarantee the probed
# line's train falls outside it unless the server filters first.
SIBLING_COUNT = 60

# The Main train has to depart after every sibling (so the limit really does
# hide it) while staying inside the window the endpoint queries by default:
# today 00:00 ET through +26h. That headroom shrinks as the day advances and
# bottoms out at ~120 minutes just before midnight, so a fixed +180 put the
# train past the window — and failed both scoped tests — on any run after
# 23:00 ET. Sits clear of both bounds: SIBLING_COUNT + 5 < 90 < 120.
MAIN_DEPARTURE_OFFSET_MINUTES = 90


def _seed_journey(session, *, train_id, line_code, departs_in_minutes):
    """Persist one upcoming NJT journey with an origin and a terminal stop."""
    departure = now_et() + timedelta(minutes=departs_in_minutes)
    arrival = departure + timedelta(minutes=50)
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        data_source="NJT",
        line_code=line_code,
        line_name=f"Line {line_code}",
        line_color="#00A94F",
        destination="Suffern",
        origin_station_code=ORIGIN,
        terminal_station_code=TERMINAL,
        scheduled_departure=departure,
        first_seen_at=now_et() - timedelta(minutes=30),
        last_updated_at=now_et(),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code=ORIGIN,
            station_name="Hoboken",
            scheduled_departure=departure,
            updated_departure=departure,
            stop_sequence=0,
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        ),
        JourneyStop(
            station_code=TERMINAL,
            station_name="Suffern",
            scheduled_arrival=arrival,
            updated_arrival=arrival,
            stop_sequence=1,
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        ),
    ]
    session.add(journey)
    return journey


@pytest.fixture(autouse=True)
def reset_counters(monkeypatch):
    """The script reports through module-level counters; isolate each test."""
    monkeypatch.setattr(gtv, "PASS_COUNT", 0)
    monkeypatch.setattr(gtv, "FAIL_COUNT", 0)
    monkeypatch.setattr(gtv, "WARN_COUNT", 0)
    monkeypatch.setattr(gtv, "SKIP_COUNT", 0)


@pytest.fixture
def busy_shared_terminal(sync_session):
    """60 Bergen trains ahead of a single, later Main train on HB -> SF."""
    for i in range(SIBLING_COUNT):
        _seed_journey(
            sync_session,
            train_id=f"BERGEN_{i}",
            line_code=BERGEN,
            departs_in_minutes=5 + i,
        )
    _seed_journey(
        sync_session,
        train_id="MAIN_1",
        line_code=MAIN,
        departs_in_minutes=MAIN_DEPARTURE_OFFSET_MINUTES,
    )
    sync_session.commit()


class TestLineProbeAgainstRealEndpoint:
    def test_unscoped_request_loses_the_line_behind_the_limit(
        self, e2e_client: TestClient, busy_shared_terminal
    ):
        """The regression itself, measured on the real server.

        Without this, the scoped test below would pass for free — it is this
        assertion that proves the fixture really is #1629's shape and that the
        limit, not the fixture, is what hides the Main train.
        """
        deps = gtv.fetch_trackrat_departures(
            e2e_client, BASE_URL, ORIGIN, TERMINAL, "NJT"
        )

        assert len(deps) == 50, "the endpoint's limit must be the binding constraint"
        assert {d.line_code for d in deps} == {BERGEN}
        assert "MAIN_1" not in {d.train_id for d in deps}, (
            "the Main train sits past row 50 of the unscoped result; "
            "filtering the response in Python can never recover it"
        )

    def test_scoped_probe_surfaces_the_line_the_limit_would_have_truncated(
        self, e2e_client: TestClient, busy_shared_terminal
    ):
        deps, direction, errors = gtv._probe_line_departures(
            e2e_client, BASE_URL, "NJT", STATIONS, frozenset({MAIN})
        )

        assert [d.train_id for d in deps] == ["MAIN_1"], (
            "the server applies `lines` before the limit, so the probed line's "
            "only train must survive 60 earlier siblings"
        )
        assert direction == f"{ORIGIN}->{TERMINAL}"
        assert errors == [], "a correctly filtered response is not a violation"
        assert gtv.FAIL_COUNT == 0

    def test_scoped_response_carries_no_sibling_rows(
        self, e2e_client: TestClient, busy_shared_terminal
    ):
        """The contract the probe now asserts, verified against the real server."""
        deps = gtv.fetch_trackrat_departures(
            e2e_client, BASE_URL, ORIGIN, TERMINAL, "NJT", lines=frozenset({MAIN})
        )

        assert gtv.scoped_line_violations(deps, frozenset({MAIN})) == []
        assert {d.line_code for d in deps} == {MAIN}

    def test_multi_code_scope_matches_the_stored_case_variant(
        self, e2e_client: TestClient, sync_session
    ):
        """NJT stores case variants of one line; the whole set must be sent.

        The server matches line codes raw, so a probe that sent only "MA" would
        report a running Montclair-Boonton line as dark.
        """
        _seed_journey(
            sync_session, train_id="MONTCLAIR_1", line_code="Ma", departs_in_minutes=20
        )
        sync_session.commit()

        deps, _direction, errors = gtv._probe_line_departures(
            e2e_client, BASE_URL, "NJT", STATIONS, frozenset({"MA", "Ma"})
        )

        assert [d.train_id for d in deps] == ["MONTCLAIR_1"]
        assert errors == []

        single_code = gtv.fetch_trackrat_departures(
            e2e_client, BASE_URL, ORIGIN, TERMINAL, "NJT", lines=frozenset({"MA"})
        )
        assert single_code == [], "the server does not case-fold; both codes matter"

    def test_genuinely_dark_line_is_empty_without_a_contract_failure(
        self, e2e_client: TestClient, busy_shared_terminal
    ):
        """A line with no trains is a coverage question, never a filter bug."""
        deps, direction, errors = gtv._probe_line_departures(
            e2e_client, BASE_URL, "NJT", STATIONS, frozenset({"XX"})
        )

        assert deps == []
        assert direction == f"{ORIGIN}<->{TERMINAL}"
        assert errors == []
        assert gtv.FAIL_COUNT == 0, "an empty line must not raise a FAIL here"
