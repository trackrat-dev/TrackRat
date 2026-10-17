"""The startup script's output must reach Cloud Logging, not just the VM (#1829).

The instance startup script is the only thing standing between a recreated VM
and a serving instance: it attaches the data disk, installs compose, fetches
secrets, downloads config, pulls images, runs migrations and starts containers.
Every one of those steps used to be silent remotely, because the script opened
with

    exec > /var/log/startup.log 2>&1

GCE ships startup-script stdout to the serial console and to Cloud Logging
automatically (this template sets ``google-logging-enabled``), so that redirect
opted the entire boot out of remote observability. During the 2026-09-20 outage
the instance was visibly up and the API visibly down while Cloud Logging held
only kernel/systemd/audit noise; the line that actually explained it —

    CommandException: No URLs matched: gs://trackrat-v2-deploy-production/docker-compose.yml

— was reachable only by SSH, and cost roughly 20 minutes of a 33-minute outage.

The fix is to tee rather than redirect, keeping the on-disk copy for SSH-based
forensics while the same output becomes queryable via
``.claude/scripts/gcp-logs.py`` and usable by log-based metrics.

The last test here does not assert on text: it lifts the real ``exec`` line out
of ``compute.tf`` and runs it under bash, so what is verified is that output
genuinely lands in *both* places. A textual guard alone would pass for a line
that happened to mention ``tee`` while still swallowing stdout.
"""

import re
import subprocess
from pathlib import Path

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"


def _startup_script() -> str:
    """Everything before the shutdown-script block, matching how the existing
    infra tests (test_cloudflare_tunnel_isolation, test_staging_scrub_sql)
    slice this file."""
    return _COMPUTE_TF.read_text().split("shutdown-script", 1)[0]


def _shutdown_script() -> str:
    return _COMPUTE_TF.read_text().split("shutdown-script", 1)[1]


def _exec_line() -> str:
    """The startup script's stdout/stderr setup line, dedented out of the
    Terraform heredoc."""
    matches = [
        line.strip()
        for line in _startup_script().splitlines()
        if line.strip().startswith("exec ")
    ]
    assert len(matches) == 1, (
        "expected exactly one `exec` redirection line in the startup script so "
        f"this guard cannot silently target the wrong one; found: {matches}"
    )
    return matches[0]


def test_startup_script_does_not_redirect_stdout_away_from_cloud_logging():
    """The specific regression: a bare `exec > FILE` discards the stream GCE
    forwards to Cloud Logging."""
    line = _exec_line()
    assert not re.match(r"^exec\s*>\s*/var/log/startup\.log", line), (
        "the startup script redirects stdout straight to a file, which opts the "
        "entire boot out of Cloud Logging and the serial console — a failed boot "
        "then leaves no remote signal at all and needs SSH to diagnose "
        f"(issue #1829). Line was: {line!r}"
    )


def test_startup_script_tees_to_both_the_log_file_and_stdout():
    """The on-disk copy must survive too — it is what SSH-based forensics reads,
    and dropping it in favour of journald alone would trade one blind spot for
    another."""
    line = _exec_line()
    assert "tee" in line and "/var/log/startup.log" in line, (
        "the startup script must tee to /var/log/startup.log so output reaches "
        f"BOTH Cloud Logging and the VM (issue #1829). Line was: {line!r}"
    )


def test_shutdown_script_still_tees():
    """compute.tf's shutdown path has always used `| tee -a`; issue #1829's
    argument is that startup should match it. If someone 'simplifies' shutdown
    into a plain redirect later, the precedent — and the shutdown-time
    diagnostics — go with it."""
    shutdown = _shutdown_script()
    assert "tee -a /var/log/shutdown.log" in shutdown, (
        "the shutdown script must keep teeing to /var/log/shutdown.log; it is "
        "the pattern startup was aligned to (issue #1829)"
    )


def test_the_real_exec_line_delivers_output_to_both_destinations(tmp_path):
    """Execute the actual line from compute.tf rather than asserting about it.

    This is the assertion that matters: a line can mention `tee` and still fail
    to reach one destination (e.g. `exec > >(tee -a FILE) >/dev/null`). Running
    it proves the property the issue is about.
    """
    log_path = tmp_path / "startup.log"
    exec_line = _exec_line().replace("/var/log/startup.log", str(log_path))

    marker_stdout = "BOOT-STEP-MARKER-stdout"
    marker_stderr = "BOOT-STEP-MARKER-stderr"
    script = "\n".join(
        [
            "#!/bin/bash",
            "set -e",
            exec_line,
            f"echo {marker_stdout}",
            # 2>&1 is part of the real line, so a step that writes to stderr
            # (every gsutil/toolbox failure does) must be captured as well.
            f"echo {marker_stderr} >&2",
            # Give the tee subprocess a moment to flush before the shell exits;
            # process substitution is not reaped synchronously.
            "sleep 0.2",
            "",
        ]
    )
    script_path = tmp_path / "startup_fragment.sh"
    script_path.write_text(script)

    proc = subprocess.run(
        ["bash", str(script_path)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, (
        f"the extracted exec line did not run cleanly under bash: {proc.stderr!r}. "
        "Note process substitution `>(...)` is a bash feature — a switch to "
        "#!/bin/sh would break this line silently."
    )

    captured = proc.stdout + proc.stderr
    assert marker_stdout in captured and marker_stderr in captured, (
        "startup output must still reach the script's own stdout — that is the "
        "stream GCE forwards to the serial console and Cloud Logging "
        f"(issue #1829). Captured: {captured!r}"
    )

    assert log_path.is_file(), "the on-disk log file was never created"
    on_disk = log_path.read_text()
    assert marker_stdout in on_disk and marker_stderr in on_disk, (
        "startup output must also still land in /var/log/startup.log for "
        f"SSH-based forensics (issue #1829). File held: {on_disk!r}"
    )
