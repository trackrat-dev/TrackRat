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
under ``bash -e``, because what matters is control flow — the prune happens
after every ``up``, and a prune failure cannot abort the boot — not that the
text is present.

On the ``docker`` / compose stand-ins, and AGENTS.md's "do not use mock services
for anything ever": the subject under test — the startup script's control flow —
is sliced verbatim out of ``compute.tf`` and executed, not stubbed. What cannot
be real is the VM's Docker daemon holding the deployment's images and starting
its containers; running the real ``compose up -d`` here would start the
production stack on the CI runner. The stand-ins only record the order of calls
and return a chosen exit status. This is the same decision taken for
``toolbox`` in ``test_compose_download_fallback.py`` and
``test_cloudflare_tunnel_isolation.py``.
"""

import subprocess
import textwrap
from pathlib import Path

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"

_BLOCK_START = "# Start all containers"
_BLOCK_END = 'echo "Completed at:'
_PRUNE = "docker image prune -f"

_DOCKER_STUB = """#!/bin/bash
echo "docker $*" >> "$STUB_CALL_LOG"
exit "$STUB_DOCKER_EXIT"
"""

_COMPOSE_STUB = """#!/bin/bash
echo "compose $*" >> "$STUB_CALL_LOG"
"""


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


def _run_tail(tmp_path: Path, *, docker_exit: int) -> tuple:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, content in (("docker", _DOCKER_STUB), ("compose", _COMPOSE_STUB)):
        stub = bin_dir / name
        stub.write_text(content)
        stub.chmod(0o755)

    call_log = tmp_path / "calls.log"
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "COMPOSE_PATH": str(bin_dir / "compose"),
        # Enabled, so the connector bring-up runs too and the prune is checked
        # against the last `up` the script performs, not just the first.
        "TUNNEL_ENABLED": "1",
        "STUB_CALL_LOG": str(call_log),
        "STUB_DOCKER_EXIT": str(docker_exit),
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


def test_prune_runs_after_every_bring_up(tmp_path):
    """After the last `up`, every image still wanted is held by a running
    container or still tagged, so a dangling-only prune removes exactly the
    superseded ones. The exact argv also pins "dangling only": `-a` would delete
    every image no container uses — on COS that includes the toolbox image the
    startup script needs on every boot, re-pulled each time."""
    proc, calls = _run_tail(tmp_path, docker_exit=0)
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, f"bring-up tail failed. Output was:\n{output}"
    assert calls == [
        "compose up -d",
        "compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --no-deps cloudflared",
        "docker image prune -f",
    ], (
        "expected the full-stack up, then the connector up, then exactly one "
        "dangling-image prune. Calls were:\n" + "\n".join(calls)
    )


def test_failed_prune_does_not_abort_the_boot(tmp_path):
    """The containers are already up when the prune runs. A failure there is a
    housekeeping miss, never a reason for `set -e` to end the startup script."""
    proc, calls = _run_tail(tmp_path, docker_exit=1)
    output = proc.stdout + proc.stderr

    assert "docker image prune -f" in calls, (
        "the failing prune was never invoked, so this test proved nothing. "
        "Calls were:\n" + "\n".join(calls)
    )
    assert (
        proc.returncode == 0
    ), f"a failed image prune aborted the startup script. Output was:\n{output}"
    assert (
        "BOOT_COMPLETED" in proc.stdout
    ), f"the script stopped before its end. Output was:\n{output}"
    assert (
        "WARN: docker image prune failed" in output
    ), f"a failed prune must be reported in the startup log. Output was:\n{output}"
