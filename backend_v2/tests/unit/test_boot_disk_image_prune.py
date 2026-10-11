"""Superseded images must not accumulate on the boot disk (issue #1879).

Production deploys with ``rolling-action restart`` (``infra_v2/cloudbuild.yaml``):
the same VM is stopped and started, so its boot disk — and every image ever
pulled onto it — persists across deploys. Each boot's ``compose pull`` moves the
``api:<env>-latest`` tag to the new image and leaves the previous one dangling.
Nothing removed those, so production's boot disk grew by one api image per
deploy with no bound, on the same disk whose exhaustion silenced all logging for
19 days (issues #1825/#1826). Staging cannot show this: its deploys resize the
MIG to 0 and back to 1, so every staging deploy boots a fresh disk.

The startup script now runs ``docker image prune -f`` after the bring-up. These
tests **execute** that tail of the real startup script out of ``compute.tf``
under ``bash -e`` against the **real** Docker CLI and daemon, reproducing a
deploy's retag: an image superseded under the same tag must be removed, the
tagged image must stay, and a prune that fails must not abort the boot.

Docker is real, per AGENTS.md's "do not use mock services for anything ever".
The one stand-in is ``$COMPOSE_PATH``: a real ``compose up -d`` would start the
production stack on the runner. It only logs its arguments and — via the real
``docker image inspect`` — whether the superseded image still existed when it
ran, which is what proves the prune comes after every ``up``. Same decision as
for ``toolbox`` in ``test_compose_download_fallback.py``.

The retag test prunes **every** dangling image on the daemon it talks to, so it
runs only under CI (ephemeral runners), never against a developer's daemon.
In CI a missing daemon fails rather than skips, so the check cannot silently
stop running.
"""

import os
import shutil
import subprocess
import textwrap
import uuid
from pathlib import Path

import pytest

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"

_BLOCK_START = "# Start all containers"
_BLOCK_END = 'echo "Completed at:'
_PRUNE = "docker image prune -f"

_DOCKER = shutil.which("docker")
_IN_CI = bool(os.environ.get("CI"))

_COMPOSE_STAND_IN = """#!/bin/bash
if docker image inspect "$SUPERSEDED_IMAGE" >/dev/null 2>&1; then
  state=present
else
  state=absent
fi
echo "compose $* | superseded=$state" >> "$CALL_LOG"
"""


def _daemon_reachable() -> bool:
    if _DOCKER is None:
        return False
    probe = subprocess.run(
        [_DOCKER, "info"], capture_output=True, text=True, check=False
    )
    return probe.returncode == 0


def _require_docker(*, daemon: bool) -> None:
    """Skip off-CI when Docker is unavailable; in CI, fail instead."""
    available = _daemon_reachable() if daemon else _DOCKER is not None
    if available:
        return
    what = "a reachable Docker daemon" if daemon else "the docker CLI"
    assert not _IN_CI, f"no {what} on this CI runner — the prune is unverified"
    pytest.skip(f"needs {what}")


def _extract_bring_up_tail() -> str:
    """Slice the startup script from the full-stack `up` to its last line."""
    startup = _COMPUTE_TF.read_text().split("shutdown-script", 1)[0]
    assert _BLOCK_START in startup, "full-stack bring-up not found in compute.tf"
    assert _BLOCK_END in startup, "startup script's final line not found"

    block = startup.split(_BLOCK_START, 1)[1].split(_BLOCK_END, 1)[0]
    # Re-attach the marker: the split lands mid-comment, and the rest of that
    # line would otherwise run as a command.
    body = textwrap.dedent(f"{_BLOCK_START}{block}")
    assert "$COMPOSE_PATH up -d" in body, "slice lost the full-stack bring-up"
    assert "up -d --no-deps cloudflared" in body, "slice lost the connector bring-up"
    assert body.count(_PRUNE) == 1, (
        f"expected exactly one `{_PRUNE}` after the bring-up; found "
        f"{body.count(_PRUNE)}"
    )
    return body


def _build_image(context: Path, marker: str) -> str:
    """Build an untagged one-file image offline (FROM scratch); return its id."""
    context.mkdir()
    (context / "marker").write_text(marker)
    (context / "Dockerfile").write_text("FROM scratch\nCOPY marker /marker\n")
    proc = subprocess.run(
        [_DOCKER, "build", "-q", str(context)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"docker build failed:\n{proc.stdout}{proc.stderr}"
    return proc.stdout.strip()


def _point_tag(image: str, tag: str) -> None:
    """Move `tag` onto `image`, as a `compose pull` of a newer image does.

    Not `docker build -t`: under the containerd image store a build that
    overwrites a tag deletes the previous image outright, which is not what a
    pull does and would leave nothing for the prune to find."""
    subprocess.run([_DOCKER, "tag", image, tag], check=True, capture_output=True)


def _image_id(image: str) -> str:
    proc = subprocess.run(
        [_DOCKER, "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def _image_exists(image: str) -> bool:
    proc = subprocess.run(
        [_DOCKER, "image", "inspect", image], capture_output=True, check=False
    )
    return proc.returncode == 0


def _run_tail(tmp_path: Path, *, superseded: str, extra_env: dict) -> tuple:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    compose = bin_dir / "compose"
    compose.write_text(_COMPOSE_STAND_IN)
    compose.chmod(0o755)

    call_log = tmp_path / "calls.log"
    env = {
        "PATH": f"{bin_dir}:{Path(_DOCKER).parent}:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", str(tmp_path)),
        "COMPOSE_PATH": str(compose),
        # Enabled, so the connector bring-up runs too and the prune is checked
        # against the last `up` the script performs, not just the first.
        "TUNNEL_ENABLED": "1",
        "CALL_LOG": str(call_log),
        "SUPERSEDED_IMAGE": superseded,
        **extra_env,
    }
    script = f"#!/bin/bash\nset -e\n{_extract_bring_up_tail()}\necho BOOT_COMPLETED\n"
    script_path = tmp_path / "bring_up_tail.sh"
    script_path.write_text(script)

    proc = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    calls = call_log.read_text().splitlines() if call_log.exists() else []
    return proc, calls


def test_prune_removes_the_superseded_image_after_every_bring_up(tmp_path):
    """A deploy's retag, for real: the old image loses its tag to the new one.

    The prune must remove the superseded image, keep the tagged one — the same
    reason the COS toolbox image and a cached image kept by a failed pull
    survive — and run only after both `up`s, so nothing a bring-up needs can
    already be gone. `-a` would also delete every tagged image no container
    uses, which this test catches by checking the tagged image survives."""
    if not _IN_CI:
        pytest.skip("prunes every dangling image on the daemon; CI runners only")
    _require_docker(daemon=True)

    tag = f"trackrat-prune-test-{uuid.uuid4().hex[:12]}:latest"
    superseded = current = ""
    try:
        superseded = _build_image(tmp_path / "previous", "previous deploy")
        _point_tag(superseded, tag)
        current = _build_image(tmp_path / "current", "this deploy")
        _point_tag(current, tag)
        assert superseded != current, "both builds produced the same image"
        assert _image_exists(superseded) and _image_id(tag) == current, (
            "setup did not leave a superseded, untagged image beside the tagged "
            "one, so the prune assertions below would prove nothing"
        )

        proc, calls = _run_tail(tmp_path, superseded=superseded, extra_env={})
        output = proc.stdout + proc.stderr

        assert proc.returncode == 0, f"bring-up tail failed. Output was:\n{output}"
        assert calls == [
            "compose up -d | superseded=present",
            "compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d "
            "--no-deps cloudflared | superseded=present",
        ], (
            "both bring-ups must run, in order, before anything is pruned. "
            "Calls were:\n" + "\n".join(calls)
        )
        assert not _image_exists(superseded), (
            f"the superseded image {superseded} survived the prune, so every "
            f"deploy still leaves one behind. Output was:\n{output}"
        )
        assert _image_exists(tag), (
            f"the prune removed the tagged image {tag}; it must be dangling-only. "
            f"Output was:\n{output}"
        )
    finally:
        leftovers = [ref for ref in (tag, superseded, current) if ref]
        subprocess.run([_DOCKER, "rmi", "-f", *leftovers], capture_output=True)


def test_failed_prune_does_not_abort_the_boot(tmp_path):
    """The containers are already up when the prune runs. A failure there is a
    housekeeping miss, never a reason for `set -e` to end the startup script.

    The failure is real: the docker CLI pointed at a socket nothing listens on,
    i.e. the daemon being unavailable."""
    _require_docker(daemon=False)
    dead_socket = f"unix://{tmp_path / 'no-daemon.sock'}"

    proc, calls = _run_tail(
        tmp_path,
        superseded="trackrat-prune-test-unused",
        extra_env={"DOCKER_HOST": dead_socket},
    )
    output = proc.stdout + proc.stderr

    assert (
        len(calls) == 2
    ), "both bring-ups must have run before the prune. Calls were:\n" + "\n".join(calls)
    assert (
        proc.returncode == 0
    ), f"a failed image prune aborted the startup script. Output was:\n{output}"
    assert (
        "BOOT_COMPLETED" in proc.stdout
    ), f"the script stopped before its end. Output was:\n{output}"
    assert (
        "WARN: docker image prune failed" in output
    ), f"a failed prune must be reported in the startup log. Output was:\n{output}"
