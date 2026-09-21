"""Container logs must be bounded, or they fill the boot disk (issue #1825).

Docker's default ``json-file`` driver is unbounded, and container logs are
written to ``/var/lib/docker/containers`` on the **boot** disk — 10 GB, sized on
the premise that only container images live there. Application state is on the
separate data disk, so nothing else about the deployment hints that the boot
disk grows at all.

With no ``logging:`` block on either service, the boot disk filled in roughly
two weeks (process start 2026-08-18, logs died 2026-09-01). Once it was full
Docker could not write container logs at all:

    level=error msg="Error writing log message" driver=json-file
    error="... no space left on device"

which silently stopped **every** application log from reaching Cloud Logging for
19 days, until 2026-09-20. Nothing alerted. ``/health`` inspects only the data
disk (healthy throughout at ~57%), and the log-based metrics that would have
caught it stopped receiving data points for the same reason they existed.
Debugging the concurrent NJT quota incident had to be done from Prometheus
counters and code reading, because the logs simply did not exist.

The guard here is deliberately **per-service and generic** rather than a check
that two specific services are configured: the failure mode is a *new* service
being added without rotation, which is exactly how this happened. That includes
``docker-compose.tunnel.yml`` — cloudflared runs on the same host and writes to
the same boot disk, so the issue's "both services" is necessary but not
sufficient.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

# backend_v2/tests/unit/<this file> -> backend_v2 is parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_BASE_COMPOSE = _BACKEND_DIR / "docker-compose.yml"
_TUNNEL_COMPOSE = _BACKEND_DIR / "docker-compose.tunnel.yml"

_COMPOSE_FILES = (_BASE_COMPOSE, _TUNNEL_COMPOSE)

# The boot disk is 10 GB and holds ~0.6 GB of container images
# (infra_v2/terraform/compute.tf). A total log budget anywhere near that is not
# a fix. 2 GB leaves the disk with room an order of magnitude above what the
# logs can claim.
_MAX_TOTAL_LOG_BUDGET_BYTES = 2 * 1024**3

_SIZE_SUFFIXES = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def _parse_size(value: str) -> int:
    """Docker's log-size syntax: an integer with an optional b/k/m/g suffix."""
    match = re.fullmatch(r"(\d+)\s*([bkmg])?", str(value).strip().lower())
    assert match, (
        f"max-size {value!r} is not a size Docker accepts (e.g. '50m'); an "
        "unparseable value is silently rejected and the log stays unbounded"
    )
    return int(match.group(1)) * _SIZE_SUFFIXES[match.group(2) or "b"]


def _services(path: Path) -> dict:
    assert path.is_file(), f"expected a compose file at {path}"
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    services = data.get("services") or {}
    assert services, f"{path} defines no services"
    return services


def _all_services() -> list[tuple[Path, str, dict]]:
    return [
        (path, name, body)
        for path in _COMPOSE_FILES
        for name, body in _services(path).items()
    ]


def test_every_service_configures_bounded_log_rotation():
    """The core invariant. Parameterised over whatever services exist, so a
    service added later is covered without anyone remembering to extend this."""
    for path, name, body in _all_services():
        logging_config = body.get("logging")
        assert logging_config, (
            f"service {name!r} in {path.name} has no `logging:` block, so it "
            "inherits Docker's unbounded json-file default and writes without "
            "limit to the 10 GB boot disk. That filled the disk and killed all "
            "log shipping to Cloud Logging for 19 days (issue #1825)."
        )

        options = logging_config.get("options") or {}
        assert "max-size" in options, (
            f"service {name!r} in {path.name} sets a logging driver but no "
            "max-size, which leaves the log unbounded — the driver alone changes "
            "nothing (issue #1825)"
        )
        assert "max-file" in options, (
            f"service {name!r} in {path.name} sets max-size but no max-file. "
            "Docker keeps rotated files indefinitely without it, so total growth "
            "is still unbounded (issue #1825)"
        )

        assert (
            _parse_size(options["max-size"]) > 0
        ), f"service {name!r} in {path.name} has a zero max-size"
        assert (
            int(options["max-file"]) >= 1
        ), f"service {name!r} in {path.name} has a max-file below 1"


def test_the_json_file_driver_is_the_one_being_bounded():
    """max-size/max-file are json-file options. Under a different driver they
    are accepted-looking but meaningless, so the pairing has to be checked."""
    for path, name, body in _all_services():
        driver = (body.get("logging") or {}).get("driver")
        assert driver == "json-file", (
            f"service {name!r} in {path.name} uses log driver {driver!r}. "
            "max-size/max-file are json-file options; under another driver they "
            "do not bound anything. If a different driver is genuinely wanted, "
            "this test needs updating along with the boot-disk reasoning in "
            "docker-compose.yml's header (issue #1825)."
        )


def test_total_log_budget_stays_small_against_the_boot_disk():
    """Rotation that is configured but enormous is the same bug with more steps."""
    total = 0
    breakdown = []
    for path, name, body in _all_services():
        options = (body.get("logging") or {}).get("options") or {}
        budget = _parse_size(options["max-size"]) * int(options["max-file"])
        total += budget
        breakdown.append(f"{path.name}:{name}={budget / 1024**2:.0f}MB")

    assert total <= _MAX_TOTAL_LOG_BUDGET_BYTES, (
        f"container logs may claim up to {total / 1024**3:.2f} GB of the 10 GB "
        f"boot disk ({', '.join(breakdown)}), which is too close to the failure "
        "this rotation exists to prevent (issue #1825)"
    )


def test_cloudflared_is_covered_too():
    """Explicitly named because the issue says 'both services in
    docker-compose.yml'. The connector is in a separate file (#1578) but runs on
    the same host and writes to the same boot disk, so bounding only the first
    file would leave a third unbounded writer behind."""
    services = _services(_TUNNEL_COMPOSE)
    assert "cloudflared" in services, "tunnel compose no longer defines cloudflared"
    assert (
        (services["cloudflared"].get("logging") or {})
        .get("options", {})
        .get("max-size")
    ), "cloudflared must bound its logs like db/api — same boot disk (issue #1825)"


# --------------------------------------------------------------------------- #
# Verified through the real compose binary, not just the YAML
# --------------------------------------------------------------------------- #
# A structurally valid `logging:` block can still be rejected or reshaped by
# compose's own loader. Running the real CLI over the real files — merged the
# same way the startup script merges them — is what proves Docker would actually
# apply these limits. Mirrors test_cloudflare_tunnel_isolation.py.


def _compose_argv() -> list | None:
    for argv in (["docker", "compose"], ["docker-compose"]):
        probe = subprocess.run(
            [*argv, "version"], capture_output=True, text=True, check=False
        )
        if probe.returncode == 0:
            return argv
    return None


_COMPOSE_ARGV = _compose_argv()
requires_compose = pytest.mark.skipif(
    _COMPOSE_ARGV is None,
    reason="needs a real docker compose binary to resolve the merged config",
)


def test_compose_binary_is_present_in_ci():
    """A skip is fine on a dev box; in CI it would mean the check below silently
    stopped running while the job still reported green."""
    if not os.environ.get("CI"):
        pytest.skip("compose availability is only enforced in CI")
    assert _COMPOSE_ARGV is not None, (
        "no docker compose binary on this runner — the resolved-config check "
        "would skip, leaving the #1825 rotation unverified against real compose"
    )


@requires_compose
def test_real_compose_resolves_bounded_logging_for_every_service():
    """The merged, interpolated config compose would actually run with."""
    env = {
        **os.environ,
        "DATA_DIR": "/mnt/disks/data",
        "IMAGE_URL": "example.invalid/trackrat/api:latest",
        "DB_PASSWORD": "test",
        "NJT_API_TOKEN": "test",
        "APNS_TEAM_ID": "test",
        "APNS_KEY_ID": "test",
        "APNS_BUNDLE_ID": "test",
        "CLOUDFLARE_TUNNEL_TOKEN": "test",
    }
    proc = subprocess.run(
        [
            *_COMPOSE_ARGV,
            "-f",
            str(_BASE_COMPOSE),
            "-f",
            str(_TUNNEL_COMPOSE),
            "config",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_BACKEND_DIR),
        check=False,
    )
    assert proc.returncode == 0, (
        f"compose rejected the merged config after the rotation change:\n"
        f"{proc.stderr}"
    )

    resolved = yaml.safe_load(proc.stdout)
    for name, body in (resolved.get("services") or {}).items():
        options = (body.get("logging") or {}).get("options") or {}
        assert options.get("max-size") and options.get("max-file"), (
            f"compose resolved service {name!r} without bounded log options: "
            f"{body.get('logging')!r} (issue #1825)"
        )
