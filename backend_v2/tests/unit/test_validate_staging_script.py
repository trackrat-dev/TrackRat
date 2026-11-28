"""validate-staging.sh must run every requested step after one fails (#2002).

The script used to call ``exit 1`` from ``step_fail``, so a single E2E failure
ended the run before the log check, ground truth and the coverage sweep. Twice
against production the E2E failures were time-of-day false positives, and the
steps that would have shown the real problem never ran.

These tests run the real script under bash. It is copied into a temporary
repo layout where each step's command (verify-deployment.sh, e2e-api-test.sh,
gcp-logs.py, and ``poetry`` for ground truth/coverage) is a small stand-in that
appends its name to a run log and exits with a configured code. That keeps the
step programs out of the test, so what's verified is the orchestration: which
steps ran, the summary, and the exit status. The step-1 reachability probe
hits the application's real ``/health/live`` route, served by uvicorn
(reachable), or a closed port (unreachable).
"""

import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI

from trackrat.api import health

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "validate-staging.sh"

_STEP_STUB = """#!/usr/bin/env bash
echo "{name}" >> "$RUN_LOG"
exit "${{{exit_var}:-0}}"
"""

_LOGS_STUB = """import os, sys
with open(os.environ["RUN_LOG"], "a") as f:
    f.write("logs\\n")
sys.exit(int(os.environ.get("LOGS_EXIT", "0")))
"""

# ``poetry run python3 ../scripts/ground-truth-validate.py URL --all|--coverage``
_POETRY_STUB = """#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in
    --all) echo "ground_truth" >> "$RUN_LOG"; exit "${GT_EXIT:-0}" ;;
    --coverage) echo "coverage" >> "$RUN_LOG"; exit "${COVERAGE_EXIT:-0}" ;;
  esac
done
echo "unexpected poetry invocation: $*" >&2
exit 2
"""


@pytest.fixture
def live_server() -> Iterator[str]:
    """The application's real health router, served over HTTP by uvicorn."""
    app = FastAPI()
    app.include_router(health.router)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert (
            thread.is_alive() and time.monotonic() < deadline
        ), "uvicorn did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join()
        sock.close()


@pytest.fixture
def closed_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A repo layout the script resolves SCRIPT_DIR / REPO_ROOT against."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(_SCRIPT, scripts / "validate-staging.sh")
    stubs = {
        scripts / "verify-deployment.sh": ("health", "HEALTH_EXIT"),
        scripts / "e2e-api-test.sh": ("e2e", "E2E_EXIT"),
    }
    for path, (name, exit_var) in stubs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_STEP_STUB.format(name=name, exit_var=exit_var))
    gcp_logs = tmp_path / ".claude" / "scripts" / "gcp-logs.py"
    gcp_logs.parent.mkdir(parents=True)
    gcp_logs.write_text(_LOGS_STUB)
    (tmp_path / "backend_v2").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    poetry = bin_dir / "poetry"
    poetry.write_text(_POETRY_STUB)
    poetry.chmod(0o755)
    # Satisfy the step-3 dependency checks so the script never runs pip.
    mods = tmp_path / "pymods"
    (mods / "google" / "oauth2").mkdir(parents=True)
    (mods / "google" / "oauth2" / "service_account.py").write_text("")
    (mods / "cryptography").mkdir()
    (mods / "cryptography" / "__init__.py").write_text("")
    return tmp_path


def _run(sandbox: Path, base_url: str, *flags: str, **exits: int):
    run_log = sandbox / "run.log"
    run_log.touch()
    env = {
        **os.environ,
        "PATH": f"{sandbox / 'bin'}:{os.environ['PATH']}",
        "PYTHONPATH": str(sandbox / "pymods"),
        "RUN_LOG": str(run_log),
        **{name: str(code) for name, code in exits.items()},
    }
    result = subprocess.run(
        ["bash", str(sandbox / "scripts" / "validate-staging.sh"), base_url, *flags],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ran = run_log.read_text().split()
    print(f"--- flags={flags} exits={exits} -> rc={result.returncode}, ran={ran}")
    print(result.stdout)
    print(result.stderr)
    return result, ran


def test_e2e_failure_still_runs_logs_ground_truth_and_coverage(
    sandbox: Path, live_server: str
) -> None:
    result, ran = _run(sandbox, live_server, "--ground-truth", "--coverage", E2E_EXIT=1)
    assert ran == [
        "health",
        "e2e",
        "logs",
        "ground_truth",
        "coverage",
    ], "an E2E failure must not skip the requested later steps"
    assert result.returncode == 1, "a failed step must still fail the run"
    assert "❌ 2 (E2E)" in result.stdout
    for step in ("1 (health)", "3 (logs)", "4 (ground truth)", "5 (line coverage)"):
        assert f"✅ {step}" in result.stdout, f"summary is missing a pass for {step}"
    assert "1 staging validation step(s) failed." in result.stdout
    assert "All staging validation steps passed." not in result.stdout


def test_every_failure_is_counted_in_the_summary(
    sandbox: Path, live_server: str
) -> None:
    result, ran = _run(
        sandbox,
        live_server,
        "--ground-truth",
        "--coverage",
        E2E_EXIT=1,
        LOGS_EXIT=1,
        GT_EXIT=1,
    )
    assert ran == ["health", "e2e", "logs", "ground_truth", "coverage"]
    assert result.returncode == 1
    assert "3 staging validation step(s) failed." in result.stdout
    assert "✅ 5 (line coverage)" in result.stdout


def test_all_steps_passing_exits_zero(sandbox: Path, live_server: str) -> None:
    result, ran = _run(sandbox, live_server, "--ground-truth", "--coverage")
    assert ran == ["health", "e2e", "logs", "ground_truth", "coverage"]
    assert result.returncode == 0
    assert "All staging validation steps passed." in result.stdout


def test_skipped_and_unrequested_steps_do_not_run(
    sandbox: Path, live_server: str
) -> None:
    result, ran = _run(sandbox, live_server, "--skip-logs", E2E_EXIT=1)
    assert ran == ["health", "e2e"], "--skip-logs and unrequested steps must not run"
    assert result.returncode == 1
    assert "3 (logs)" not in result.stdout.split("===== Summary =====")[1]


def test_health_failure_on_reachable_deployment_continues(
    sandbox: Path, live_server: str
) -> None:
    """Step 1 also fails on a live deployment, e.g. a lapsed GTFS bundle. The
    API still answers, so E2E and logs are still worth running."""
    result, ran = _run(sandbox, live_server, HEALTH_EXIT=1)
    assert ran == ["health", "e2e", "logs"]
    assert result.returncode == 1
    assert "Deployment is reachable; continuing" in result.stdout
    assert "❌ 1 (health)" in result.stdout


def test_unreachable_deployment_aborts_after_step_1(
    sandbox: Path, closed_port_url: str
) -> None:
    result, ran = _run(
        sandbox, closed_port_url, "--ground-truth", "--coverage", HEALTH_EXIT=1
    )
    assert ran == ["health"], "nothing after step 1 can say more than 'it is down'"
    assert result.returncode == 1
    assert "Deployment unreachable" in result.stdout
