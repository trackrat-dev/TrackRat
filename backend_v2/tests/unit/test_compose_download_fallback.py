"""A failed compose download must not be fatal to the boot (issue #1824).

The startup script runs under ``set -e``. The ``gsutil cp`` of
``docker-compose.yml`` was unguarded, so a failed download aborted the script
**on that line** — four lines before the script's own "Verify download" guard,
which exists for exactly this case and could therefore never run, and before the
copy already sitting on the persistent data disk at
``/mnt/disks/data/compose/docker-compose.yml`` could be used.

On 2026-09-20 a perfectly usable compose file was on that disk while the VM
served nothing for 33 minutes. ``docker ps -a`` was empty; no container was ever
created. A recoverable condition had been turned into a total outage.

The deliberate tradeoff, recorded here because it is a behaviour change rather
than a pure bugfix: falling back means a boot can come up on the *previous*
config. For a file that changes only on deploy, booting on the previous config
beats not booting at all. The hard failure is preserved for the case that
genuinely cannot be recovered — no file anywhere.

These tests **execute** the real block out of ``compute.tf`` under ``bash -e``
against a temp ``$APP_DIR`` rather than asserting on its text, because the
defect was entirely about ``set -e`` control flow: a textual check that the line
ends in ``|| echo ...`` would pass while the guard below it stayed unreachable
for some other reason. The ``toolbox`` stub mirrors the one in
``test_cloudflare_tunnel_isolation.py`` — real COS toolbox runs gsutil inside a
chroot, so the download lands in the chroot and never at ``$dest``, which is why
the script does the find+cp dance at all.
"""

import shutil
import subprocess
import textwrap
from pathlib import Path

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"

_BLOCK_START = "5. Download docker-compose.yml from GCS"
_BLOCK_END = "6. Create .env file"
_TOOLBOX_ROOT = "/var/lib/toolbox"

_TOOLBOX_STUB = """#!/bin/bash
# Emulates: toolbox --quiet gsutil cp gs://<bucket>/<object> <dest>
#
# Real COS toolbox runs gsutil inside a container whose filesystem is separate
# from the host's, so a successful download lands at <chroot>/<dest> and NOT at
# <dest>. Reproducing that is the point: the startup script's find+cp exists
# solely to bridge the gap, and a stub writing straight to $dest would skip it.
echo "toolbox $*" >> "$STUB_CALL_LOG"
if [ ! -f "$STUB_DOWNLOAD_SOURCE" ]; then
  # The exact shape of the 2026-09-20 failure: the object is simply not there.
  echo "CommandException: No URLs matched: gs://trackrat-v2-deploy-production/docker-compose.yml" >&2
  exit 1
fi
dest="${@: -1}"
chroot_dest="$STUB_TOOLBOX_ROOT/mnt/disks/data/compose/$(basename "$dest")"
mkdir -p "$(dirname "$chroot_dest")"
cp "$STUB_DOWNLOAD_SOURCE" "$chroot_dest"
"""

_ON_DISK_COMPOSE = (
    "# left by the previous boot, from the last successful deploy\nservices: {}\n"
)
_FRESH_COMPOSE = "# freshly downloaded this boot\nservices: {}\n"


def _extract_download_block(toolbox_root: Path) -> str:
    """Slice section 5 out of the real startup script, with the toolbox search
    root repointed at a temp directory."""
    startup = _COMPUTE_TF.read_text().split("shutdown-script", 1)[0]
    assert _BLOCK_START in startup, "compose-download block not found in compute.tf"
    assert _BLOCK_END in startup, "section 6 marker not found in compute.tf"

    block = startup.split(_BLOCK_START, 1)[1].split(_BLOCK_END, 1)[0]
    lines = block.splitlines()
    # Drop the closing "# ===" of section 5's banner at the top, and the opening
    # banner of section 6 at the bottom.
    while lines and (not lines[0].strip() or lines[0].strip().startswith("#")):
        lines.pop(0)
    while lines and (not lines[-1].strip() or lines[-1].strip().startswith("#")):
        lines.pop()

    body = textwrap.dedent("\n".join(lines))
    assert body.count(_TOOLBOX_ROOT) == 1, (
        f"expected exactly one {_TOOLBOX_ROOT} search root in the block so the "
        "harness' repoint cannot silently become a no-op"
    )
    assert "toolbox --quiet gsutil cp" in body, "block does not contain the download"
    assert "ERROR: docker-compose.yml not found" in body, (
        "block does not contain the verify-download guard — the slice is wrong, "
        "and the fail-fast test below would be vacuous"
    )
    body = body.replace("$${", "${")  # Terraform heredoc escaping
    return body.replace(_TOOLBOX_ROOT, str(toolbox_root))


class _BlockRun:
    def __init__(self, proc: subprocess.CompletedProcess, app_dir: Path):
        self.proc = proc
        self.app_dir = app_dir

    @property
    def output(self) -> str:
        return self.proc.stdout + self.proc.stderr

    @property
    def compose_file(self) -> Path:
        return self.app_dir / "docker-compose.yml"


def _run_download_block(
    tmp_path: Path,
    *,
    served: str | None,
    on_disk: str | None,
) -> _BlockRun:
    """Execute the block with a temp data-disk mount.

    ``served`` is what GCS hands back (None = the object is missing, i.e. the
    lifecycle rule aged it out); ``on_disk`` is what a previous boot left on the
    persistent data disk (None = a genuinely empty $APP_DIR).
    """
    mount_path = tmp_path / "mnt"
    app_dir = mount_path / "compose"
    app_dir.mkdir(parents=True)
    if on_disk is not None:
        (app_dir / "docker-compose.yml").write_text(on_disk)

    toolbox_root = tmp_path / "toolbox"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "toolbox"
    stub.write_text(_TOOLBOX_STUB)
    stub.chmod(0o755)

    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "MOUNT_PATH": str(mount_path),
        "DEPLOY_BUCKET": "trackrat-v2-deploy-production",
        "STUB_CALL_LOG": str(tmp_path / "toolbox-calls.log"),
        "STUB_TOOLBOX_ROOT": str(toolbox_root),
        "STUB_DOWNLOAD_SOURCE": "",
    }
    if served is not None:
        source = tmp_path / "served-object.yml"
        source.write_text(served)
        env["STUB_DOWNLOAD_SOURCE"] = str(source)

    # `set -e` is the whole subject of this issue — without it here, the
    # regression cannot reproduce and every test below passes vacuously.
    script = f"#!/bin/bash\nset -e\n{_extract_download_block(toolbox_root)}\n"
    script_path = tmp_path / "download_block.sh"
    script_path.write_text(script)

    proc = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return _BlockRun(proc, app_dir)


def test_failed_download_falls_back_to_the_on_disk_copy(tmp_path):
    """The 2026-09-20 shape, with the data disk preserved as it actually was."""
    run = _run_download_block(tmp_path, served=None, on_disk=_ON_DISK_COMPOSE)

    assert run.proc.returncode == 0, (
        "a failed compose download must not abort the boot when the persistent "
        "data disk already holds a usable copy — that copy was present on "
        "2026-09-20 and the script never looked at it, costing a 33-minute "
        f"outage (issue #1824). Output was:\n{run.output}"
    )
    assert (
        run.compose_file.read_text() == _ON_DISK_COMPOSE
    ), "the on-disk copy must survive a failed download untouched"
    assert "WARN" in run.output, (
        "a fallback boot must say so loudly — it may be running a previous "
        f"config. Output was:\n{run.output}"
    )


def test_missing_file_everywhere_still_fails_fast(tmp_path):
    """The guard must keep its teeth. Making the download non-fatal is only safe
    because the script still refuses to continue with no compose file at all —
    otherwise the boot would proceed to `compose up` with nothing to bring up."""
    run = _run_download_block(tmp_path, served=None, on_disk=None)

    assert run.proc.returncode != 0, (
        "with no compose file downloaded AND none on disk, the script must still "
        f"hard-fail rather than continue. Output was:\n{run.output}"
    )
    assert "ERROR: docker-compose.yml not found" in run.output, (
        "the failure must be the script's own explicit guard, not an incidental "
        f"abort somewhere else. Output was:\n{run.output}"
    )


def test_successful_download_still_overwrites_a_stale_on_disk_copy(tmp_path):
    """The fallback must not become a way to keep booting stale config.

    compute.tf's comment says the overwrite is deliberate — 'Always overwrite to
    ensure we're running the latest version (persistent disk may have stale
    copy)'. A fallback implemented as 'skip the download if a file exists' would
    satisfy the first test and silently pin every instance to whatever it booted
    with last.
    """
    run = _run_download_block(tmp_path, served=_FRESH_COMPOSE, on_disk=_ON_DISK_COMPOSE)

    assert run.proc.returncode == 0, f"clean download failed:\n{run.output}"
    assert run.compose_file.read_text() == _FRESH_COMPOSE, (
        "a successful download must overwrite the persistent disk's stale copy; "
        "the deployed config is the one that should run (compute.tf's own note)"
    )
    assert (
        "WARN" not in run.output
    ), f"a successful download must not warn about falling back:\n{run.output}"


def test_bash_is_available():
    """Every test here runs the real block; a missing bash would turn them all
    into errors rather than silent passes, but say so explicitly."""
    assert shutil.which("bash") is not None, "these tests execute the real block"
