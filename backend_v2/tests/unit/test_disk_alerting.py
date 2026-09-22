"""Structural guards for the disk-exhaustion alerting (issue #1826).

On 2026-09-01 the VM's boot disk filled. It stayed full for **19 days** with no
alert, no autohealing, and ``/health`` reporting ``healthy`` throughout. Three
compounding reasons, none of which a threshold value would have fixed:

1. every disk check pointed at the mounted data disk and explicitly not at the
   boot filesystem (issue #1344), and the data disk was genuinely healthy
   (~57% used, 15.6 GB free) the entire time;
2. the alerts are built on **log-based** metrics, so when the full disk broke
   Docker's log writing the metrics stopped receiving points — and a threshold
   condition on a metric with no data does not fire, it goes quiet. The
   monitoring intended to catch disk exhaustion was disabled by the disk
   exhaustion;
3. MIG autohealing probes ``/health/ready``, which checks Postgres and the
   scheduler — both on the healthy data disk — so it had no signal either.

These are all *shape* failures rather than tuning failures, so they are pinned
here against the real files. A future edit that drops the absence condition,
re-merges the two filesystems into one metric, or gives the absence policy an
``auto_close`` would silently re-arm the same 19-day blind spot while every
individual resource still looked reasonable in review.

The files are parsed as text by brace matching rather than through an HCL
library, matching ``test_cloudflare_tunnel_isolation.py``: no extra dependency,
and these assertions are about the presence and coupling of specific blocks.
"""

import re
from pathlib import Path

import pytest

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_METRICS_TF = _REPO_ROOT / "infra_v2" / "terraform" / "metrics.tf"
_MONITORING_TF = _REPO_ROOT / "infra_v2" / "terraform" / "monitoring.tf"
_SCHEDULER_PY = (
    _REPO_ROOT / "backend_v2" / "src" / "trackrat" / "services" / "scheduler.py"
)


def _strip_comments(hcl: str) -> str:
    """Drop whole-line ``#`` comments.

    Every assertion below is about configuration, not prose. Without this a
    comment *explaining* why a setting is absent would satisfy a check for that
    setting being absent — which these files comment heavily enough to hit.
    """
    return "\n".join(
        line for line in hcl.splitlines() if not line.lstrip().startswith("#")
    )


def _extract_block(source: str, header: str) -> str:
    """Return the body of the first block whose line starts with ``header``.

    Brace-matched, and string-literal aware so a ``{`` inside a filter or
    description doesn't end the block early. Comments are stripped from the
    result — see ``_strip_comments``.
    """
    match = re.search(rf"^{re.escape(header)}\s*\{{", source, re.MULTILINE)
    assert match, f"no block found for: {header}"

    depth = 0
    in_string = False
    escaped = False
    start = match.end() - 1

    for index in range(start, len(source)):
        char = source[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return _strip_comments(source[start + 1 : index])

    raise AssertionError(f"unbalanced braces in block: {header}")


@pytest.fixture(scope="module")
def metrics_tf() -> str:
    assert _METRICS_TF.is_file(), f"expected metrics config at {_METRICS_TF}"
    return _METRICS_TF.read_text()


@pytest.fixture(scope="module")
def monitoring_tf() -> str:
    assert _MONITORING_TF.is_file(), f"expected monitoring config at {_MONITORING_TF}"
    return _MONITORING_TF.read_text()


@pytest.fixture(scope="module")
def scheduler_py() -> str:
    return _SCHEDULER_PY.read_text()


class TestLogAbsenceAlert:
    """Reason 2: the alert path depended on the logs it was meant to protect."""

    def test_an_absence_condition_exists(self, monitoring_tf):
        """Something must alert on logs *stopping*, not just on a bad value.

        This is the only condition in the file that survives its own subject
        failing. Without it, any outage that takes log shipping down also takes
        the entire alerting stack down with it — which is what bought 19 days
        of silence.
        """
        assert "condition_absent" in monitoring_tf, (
            "no condition_absent anywhere in monitoring.tf: every alert is a "
            "threshold on a log-based metric, and a threshold on a metric "
            "receiving no data does not fire — it goes quiet"
        )

        body = _extract_block(
            monitoring_tf,
            'resource "google_monitoring_alert_policy" "application_logs_absent"',
        )
        assert "condition_absent" in body

    def test_absence_condition_watches_a_resource_usage_metric(self, monitoring_tf):
        """It must watch a metric the 15-minute check actually emits.

        An absence condition is only a heartbeat if something is reliably
        beating. Pointing it at a metric that is emitted conditionally (or not
        at all) makes it either permanently firing or permanently useless.
        """
        body = _extract_block(
            monitoring_tf,
            'resource "google_monitoring_alert_policy" "application_logs_absent"',
        )
        assert "disk_usage_percent" in body, (
            "the absence condition does not reference a disk-usage metric; "
            "those are the ones emitted unconditionally by the 15-minute "
            "check_resource_usage tick"
        )

    def test_absence_duration_tolerates_a_rolling_update(self, monitoring_tf):
        """Long enough not to page on a MIG instance recreation.

        A policy that cries wolf during routine deploys gets muted, and a muted
        absence alert is worth exactly as much as no absence alert.
        """
        body = _extract_block(
            monitoring_tf,
            'resource "google_monitoring_alert_policy" "application_logs_absent"',
        )
        duration = re.search(r'duration\s*=\s*"(\d+)s"', body)
        assert duration, "absence condition has no duration"
        seconds = int(duration.group(1))
        assert 1800 <= seconds <= 7200, (
            f"absence duration is {seconds}s; below ~30 min this fires on "
            "ordinary instance recreation, above ~2h it stops being an alert"
        )

    def test_absence_condition_reduces_across_series(self, monitoring_tf):
        """Without a cross-series reduction this pages about dead machines.

        Absence is evaluated per time series, and these series are keyed by
        instance_id. Every MIG instance recreation strands a series that
        correctly never reports again, so an unreduced policy fires forever for
        an instance that no longer exists. Collapsing to one series also asks
        the right question: not "is instance X quiet" but "are we receiving
        application logs at all".
        """
        body = _extract_block(
            monitoring_tf,
            'resource "google_monitoring_alert_policy" "application_logs_absent"',
        )
        assert "cross_series_reducer" in body, (
            "absence condition has no cross_series_reducer: it will fire "
            "permanently for every instance the MIG has ever replaced"
        )

    def test_absence_policy_does_not_auto_close(self, monitoring_tf):
        """An absence incident must not close itself while still absent.

        The threshold policies in this file auto_close after 30 minutes, which
        is fine for a value that recovers. For absence it would mean quietly
        forgetting an ongoing outage roughly as fast as it was noticed.
        """
        body = _extract_block(
            monitoring_tf,
            'resource "google_monitoring_alert_policy" "application_logs_absent"',
        )
        assert "auto_close" not in body, (
            "the absence policy auto-closes; an ongoing log outage would keep "
            "resolving itself on a timer while nothing had actually recovered"
        )


class TestBootDiskMonitoring:
    """Reason 1: nothing watched the filesystem that actually filled."""

    def test_boot_disk_metric_exists(self, metrics_tf):
        body = _extract_block(
            metrics_tf,
            'resource "google_logging_metric" "boot_disk_usage_percent"',
        )
        assert 'jsonPayload.event=\\"boot_disk_usage_check\\"' in body, (
            "boot disk metric does not filter on the boot_disk_usage_check "
            "event, so it will never receive a data point"
        )

    def test_boot_disk_is_a_separate_metric_from_the_data_disk(self, metrics_tf):
        """One series per filesystem, deliberately.

        The alerts reduce with REDUCE_MEAN. A single series carrying both
        filesystems would let a healthy data disk average a full boot disk back
        under the threshold — the exact arithmetic that made the 2026-09-01
        state look fine (100% and 57% mean 78.75%, under the 85% page).
        """
        data_body = _extract_block(
            metrics_tf,
            'resource "google_logging_metric" "data_disk_usage_percent"',
        )
        boot_body = _extract_block(
            metrics_tf,
            'resource "google_logging_metric" "boot_disk_usage_percent"',
        )
        assert 'jsonPayload.event=\\"data_disk_usage_check\\"' in data_body
        assert "boot_disk_usage_check" not in data_body, (
            "the data disk metric also matches boot disk events; the two "
            "readings would be averaged into one series"
        )
        assert "data_disk_usage_check" not in boot_body

    @pytest.mark.parametrize(
        ("policy", "threshold"),
        [
            ("boot_disk_usage_warning", 75),
            ("boot_disk_usage_critical", 85),
        ],
    )
    def test_boot_disk_alert_tiers(self, monitoring_tf, policy, threshold):
        """Two tiers, matching the data disk.

        Docker's log writing only breaks at 100%, so on a 10 GB boot disk
        filling at the observed rate (~10 GB over ~2 weeks) these leave roughly
        3.5 and 2 days of warning. That window is the entire point: the failure
        is gradual and the detection was not.
        """
        body = _extract_block(
            monitoring_tf,
            f'resource "google_monitoring_alert_policy" "{policy}"',
        )
        assert f"threshold_value = {threshold}" in body
        assert (
            "boot_disk_usage_percent" in body
        ), f"{policy} does not read the boot disk metric"


class TestSchedulerEmitsWhatTheMetricsRead:
    """The cross-file coupling that nothing else checks.

    A log-based metric is joined to the application by an event-name string in
    two files that are never compiled together. Renaming the event in
    scheduler.py leaves valid Terraform and valid Python, and a metric that
    silently receives nothing forever — indistinguishable, to every threshold
    alert, from a healthy system.
    """

    @pytest.mark.parametrize(
        "event",
        ["data_disk_usage_check", "boot_disk_usage_check", "database_size_check"],
    )
    def test_event_name_is_emitted_by_check_resource_usage(self, scheduler_py, event):
        # Must be an actual logging call: the surrounding docstrings name these
        # events too, and a docstring emits no data points.
        emitted = re.search(
            rf'logger\.(?:info|warning)\(\s*"{re.escape(event)}"', scheduler_py
        )
        assert emitted, (
            f"metrics.tf filters on jsonPayload.event={event!r} but scheduler.py "
            "never logs it; the metric would receive no data points and every "
            "threshold alert built on it would sit quietly at no-data"
        )

    def test_boot_disk_path_is_the_container_root(self, scheduler_py):
        """The boot check must sample ``/``, not the data mount again.

        On Container-Optimized OS the container's ``/`` is an overlay whose
        upper layer lives on the VM's boot disk, so this is the path that
        reports the filesystem that ran out.
        """
        match = re.search(
            r'^BOOT_DISK_PATH\s*=\s*"([^"]*)"', scheduler_py, re.MULTILINE
        )
        assert match, "BOOT_DISK_PATH is not defined in scheduler.py"
        assert match.group(1) == "/", (
            f"BOOT_DISK_PATH is {match.group(1)!r}; anything other than the "
            "container root re-creates #1826 by measuring the wrong filesystem"
        )
