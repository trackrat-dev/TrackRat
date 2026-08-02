"""Regression guards for the Cloudflare Tunnel connector isolation (issue #1578).

The 2026-07-19 staging outage happened because the ``cloudflared`` connector was
(a) gated on *secret existence* rather than a committed flag, and (b) shared the
``api``/``db`` compose file, so a bad connector token/config aborted the whole
``compose up``. The remediation:

* the connector lives in a **separate** ``docker-compose.tunnel.yml`` that the
  api/db bring-up never loads (parse-level isolation);
* it is brought up in a **second, non-fatal** ``up`` only when the committed
  ``enable_cloudflare_tunnel`` flag is true AND the token secret is present.

Issue #1594 then closed the remaining cutover gap: an enabled boot whose config
download failed could still reuse the ``docker-compose.tunnel.yml`` a previous
boot left on the persistent data disk, running an older connector definition
than the deployed Terraform revision. The connector config block now fails
closed — stale file removed up front, download to a unique temp file, validated,
then atomically installed.

These tests pin those invariants to the actual repo files so a future edit that
re-couples the connector to api/db — or reverts to secret-only gating, or to a
non-atomic download — fails loudly instead of silently re-arming the outage.
They parse the real files (no mocks), matching how the deploy pipeline and
startup script consume them, and the last group *executes* the real connector
config block out of ``compute.tf``.
"""

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

# backend_v2/tests/unit/<this file> -> backend_v2 is parents[2], repo root parents[3]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]

_BASE_COMPOSE = _BACKEND_DIR / "docker-compose.yml"
_TUNNEL_COMPOSE = _BACKEND_DIR / "docker-compose.tunnel.yml"
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"
_VARIABLES_TF = _REPO_ROOT / "infra_v2" / "terraform" / "variables.tf"


def _load(path: Path) -> dict:
    assert path.is_file(), f"expected compose file at {path}"
    with path.open() as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    return data


# --------------------------------------------------------------------------- #
# Compose file structure
# --------------------------------------------------------------------------- #


def test_base_compose_excludes_cloudflared():
    """api/db bring-up must not even reference the connector (parse isolation)."""
    services = _load(_BASE_COMPOSE).get("services", {})
    assert "db" in services and "api" in services, "base stack must define db + api"
    assert "cloudflared" not in services, (
        "cloudflared must NOT live in docker-compose.yml — a connector parse/config "
        "error there could abort the api/db bring-up (issue #1578)"
    )


def test_tunnel_compose_defines_cloudflared_and_nothing_else():
    services = _load(_TUNNEL_COMPOSE).get("services", {})
    assert list(services.keys()) == ["cloudflared"], (
        "docker-compose.tunnel.yml must define only the cloudflared connector, "
        f"got {sorted(services)}"
    )


def test_tunnel_connector_shares_trackrat_network_with_api():
    """Merged base+tunnel must keep cloudflared on the same network as api so it
    still resolves http://api:8000."""
    base = _load(_BASE_COMPOSE)
    tunnel = _load(_TUNNEL_COMPOSE)

    api_networks = base["services"]["api"].get("networks")
    cf_networks = tunnel["services"]["cloudflared"].get("networks")
    assert api_networks == ["trackrat"], api_networks
    assert cf_networks == ["trackrat"], cf_networks
    # Both files declare the network so the merged config is self-consistent.
    assert "trackrat" in base.get("networks", {})
    assert "trackrat" in tunnel.get("networks", {})


def test_tunnel_token_passed_via_env_not_inline_command():
    """The token must ride TUNNEL_TOKEN (env), never an inline --token in a string
    command — the exact shell-word-splitting trap behind the original outage."""
    cf = _load(_TUNNEL_COMPOSE)["services"]["cloudflared"]
    assert cf["environment"]["TUNNEL_TOKEN"] == "${CLOUDFLARE_TUNNEL_TOKEN}"
    command = cf.get("command", "")
    assert "--token" not in command, "token must not be an inline command flag"
    assert "${CLOUDFLARE_TUNNEL_TOKEN}" not in command


def test_tunnel_connector_not_gated_by_compose_profile():
    """Isolation is now via a separate file, not a profile in the shared file.
    A resurrected ``profiles:`` on cloudflared would mean it is back in a file the
    api/db bring-up parses."""
    cf = _load(_TUNNEL_COMPOSE)["services"]["cloudflared"]
    assert "profiles" not in cf


# --------------------------------------------------------------------------- #
# Terraform startup script + variable gating
# --------------------------------------------------------------------------- #


def test_enable_cloudflare_tunnel_variable_has_committed_boolean_default():
    """The connector must be gated by a committed default — never by secret
    presence or an ad-hoc ``-var`` (the #1578 failure mode). The flag shipped
    ``false`` until the staging cutover deliberately flipped it (see
    infra_v2/RUNBOOK-cloudflare-cutover.md); either value is a valid deliberate
    choice, but the block must keep an explicit literal boolean default so
    push-triggered applies stay consistent across workspaces."""
    text = _VARIABLES_TF.read_text()
    assert 'variable "enable_cloudflare_tunnel"' in text
    block = text.split('variable "enable_cloudflare_tunnel"', 1)[1].split(
        "variable ", 1
    )[0]
    assert "type        = bool" in block
    assert (
        "default     = true" in block or "default     = false" in block
    ), "connector gate must keep an explicit committed boolean default (issue #1578)"


def test_startup_script_gates_connector_on_flag_and_token():
    text = _COMPUTE_TF.read_text()
    # The flag is surfaced into the script and required alongside a non-empty token.
    assert 'ENABLE_CLOUDFLARE_TUNNEL="${var.enable_cloudflare_tunnel}"' in text
    assert (
        '[ "$ENABLE_CLOUDFLARE_TUNNEL" = "true" ] && [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]'
        in text
    )


def test_startup_script_dropped_secret_only_profile_activation():
    """The old failure mode: secret presence alone flipped COMPOSE_PROFILES=tunnel."""
    text = _COMPUTE_TF.read_text()
    assert "COMPOSE_PROFILES=tunnel" not in text


def test_startup_script_teardown_removes_orphaned_connector():
    """Disabling the tunnel must actually stop a previously-started connector.

    The pre-`up` teardown loads only docker-compose.yml, so cloudflared (defined
    only in the tunnel file) is an orphan there. Without --remove-orphans a
    connector started on a prior boot keeps running/restarting after the tunnel
    is turned off, which is exactly the state issue #1578 is meant to prevent.
    """
    text = _COMPUTE_TF.read_text()
    assert "$COMPOSE_PATH down --remove-orphans" in text, (
        "the pre-up teardown must use `down --remove-orphans` so a stray "
        "cloudflared from a prior boot is stopped when the tunnel is disabled"
    )


def test_startup_script_brings_connector_up_isolated_and_nonfatal():
    text = _COMPUTE_TF.read_text()
    assert (
        "-f docker-compose.yml -f docker-compose.tunnel.yml up -d --no-deps cloudflared"
        in text
    ), "connector must come up as an isolated second compose invocation"
    # Non-fatal: a connector failure must not abort the startup script.
    isolated = text.split("up -d --no-deps cloudflared", 1)[1]
    assert (
        isolated.lstrip().startswith("\\") or "|| echo" in isolated[:120]
    ), "the isolated cloudflared bring-up must be non-fatal (|| ...)"


def test_startup_script_connector_up_uses_no_deps():
    """The tunnel file declares ``depends_on: [api]``, so without --no-deps the
    connector bring-up pulls api into its scope — api is left untouched only as
    long as the merged config happens not to drift. --no-deps makes the
    "connector failure cannot touch api/db" guarantee structural (issue #1594)."""
    text = _COMPUTE_TF.read_text()
    assert "up -d --no-deps cloudflared" in text, (
        "the isolated connector bring-up must use --no-deps so api is never "
        "in scope of the tunnel-file invocation"
    )


def test_startup_script_clears_stale_tunnel_file_before_download():
    """File presence must mean "downloaded and validated this boot". $APP_DIR lives
    on the persistent data disk (staging's is cloned from production's on every
    deploy), so a tunnel file from a prior enabled boot lingers unless removed —
    and the removal has to happen *before* the enabled download attempt, not only
    on disabled boots, or a failed download silently reuses it (issue #1594)."""
    text = _COMPUTE_TF.read_text()
    startup = text.split("shutdown-script", 1)[0]
    removal = 'rm -f "$APP_DIR/docker-compose.tunnel.yml"'
    assert removal in startup, (
        "startup must remove any stale docker-compose.tunnel.yml so file presence "
        "tracks this boot, not a prior one"
    )
    # Unconditional: the removal precedes the enable check, so it covers the
    # enabled-boot path too (the fail-closed guarantee) rather than only the
    # disabled branch.
    before_gate = startup.split(
        '[ "$ENABLE_CLOUDFLARE_TUNNEL" = "true" ] && [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]',
        1,
    )[0]
    assert (
        removal in before_gate
    ), "stale connector config must be cleared before the enabled download attempt"


def test_startup_script_validates_connector_config_after_env_is_written():
    """Validation merges the api/db compose file, which interpolates ${IMAGE_URL}
    and friends out of .env — so `compose config` only succeeds once .env exists.
    Moving the connector block back above the .env write would make validation
    fail on every boot and silently disable the connector for good (issue #1594).
    """
    startup = _COMPUTE_TF.read_text().split("shutdown-script", 1)[0]
    marker = '-f "$TUNNEL_TMP" config -q'
    assert marker in startup, (
        "the downloaded connector config must be validated with `compose config` "
        "before it is installed"
    )
    env_write = startup.index("ENVEOF")
    validation = startup.index(marker)
    assert env_write < validation, (
        "the connector config download/validation must run after the .env "
        "heredoc, or compose config cannot resolve the base file's variables"
    )


def test_shutdown_script_drains_connector_before_base_stack():
    """When the tunnel is enabled, the shutdown path must stop cloudflared before
    api so the connector deregisters from Cloudflare's edge (connection draining)
    instead of dying with the VM while the edge still routes to it. The drain must
    be guarded on tunnel-file presence and non-fatal so a bad/stale tunnel file
    can never cost api/db their graceful stop (issue #1594)."""
    text = _COMPUTE_TF.read_text()
    assert "shutdown-script" in text
    shutdown = text.split("shutdown-script", 1)[1]

    drain = "-f docker-compose.yml -f docker-compose.tunnel.yml stop --timeout 3 cloudflared"
    assert drain in shutdown, "shutdown must merge the tunnel file to stop cloudflared"
    assert (
        'if [ -f "$APP_DIR/docker-compose.tunnel.yml" ]' in shutdown
    ), "the drain must be guarded on tunnel-file presence"
    drain_line = next(line for line in shutdown.splitlines() if drain in line)
    assert "|| true" in drain_line, "the drain must be non-fatal"

    after_drain = shutdown.split(drain, 1)[1]
    assert (
        "$COMPOSE_PATH stop --timeout" in after_drain
    ), "the base api/db stop must come after the connector drain"


# --------------------------------------------------------------------------- #
# Executable behaviour of the connector-config block (issue #1594)
# --------------------------------------------------------------------------- #
#
# The tests above pin the shape of the startup script; these run it. The tunnel
# config block is sliced out of the real compute.tf and executed by bash against
# a temp $APP_DIR, so the fail-closed and atomic-replacement behaviour is
# verified rather than asserted textually.
#
# Validation runs the **real** compose binary — `docker compose config -q` over
# the real backend_v2/docker-compose.yml merged with the downloaded file — so
# compose's own merging, `${VAR}` interpolation, `.env` discovery and schema
# checks are what accept or reject a download, not a reimplementation of them.
# (CI and dev boxes carry the v2 CLI plugin; the VM pins the v2.24.0 standalone
# binary. Same compose-go loader, invoked the same way.) These tests skip where
# no compose binary exists.
#
# `toolbox` is the one collaborator that cannot be real: it is a COS-only
# wrapper that runs gsutil inside a chroot against GCS with instance
# credentials, and exists on no CI runner. The stand-in reproduces the property
# the script actually has to cope with — **toolbox writes into its own chroot,
# never to the host path**, which is why the script does the find+cp dance — so
# the mount-copy flow is exercised rather than bypassed. To make that reachable
# the harness repoints the block's `/var/lib/toolbox` search root at a temp
# directory; nothing else about the block is rewritten.

_TUNNEL_BLOCK_START = "TUNNEL_ENABLED=0"
_TUNNEL_BLOCK_END = "# Write the tunnel token"
_TOOLBOX_ROOT = "/var/lib/toolbox"

_TOOLBOX_STUB = """#!/bin/bash
# Emulates: toolbox --quiet gsutil cp gs://<bucket>/<object> <dest>
#
# Real COS toolbox runs gsutil inside a container whose filesystem is separate
# from the host's, so the download lands at <chroot>/<dest> and NOT at <dest>.
# Reproducing that is the point: the startup script's find+cp exists solely to
# bridge the gap, and a stub that wrote straight to $dest would skip it.
echo "toolbox $*" >> "$STUB_CALL_LOG"
if [ ! -f "$STUB_DOWNLOAD_SOURCE" ]; then
  echo "CommandException: No URLs matched" >&2
  exit 1
fi
if [ -n "$STUB_SILENT_SUCCESS" ]; then
  # Exits 0 having produced nothing — the swallowed-failure class this issue is
  # about, and the only way the find below can be reached with no fresh file.
  exit 0
fi
dest="${@: -1}"
chroot_dest="$STUB_TOOLBOX_ROOT/mnt/disks/data/compose/$(basename "$dest")"
mkdir -p "$(dirname "$chroot_dest")"
cp "$STUB_DOWNLOAD_SOURCE" "$chroot_dest"
"""

_STALE_TUNNEL_YML = """# left behind by a previous enabled boot
services:
  cloudflared:
    image: cloudflare/cloudflared:2020.1.1
    command: tunnel --stale-definition run
"""

# A transfer that died mid-object: valid prefix, unparseable as a whole.
_TRUNCATED_TUNNEL_YML = (
    "services:\n  cloudflared:\n    image: cloudflare/cloudflared\n   command: [\n"
)


def _compose_argv() -> list | None:
    """The real compose CLI, or None when this machine has none."""
    for argv in (["docker", "compose"], ["docker-compose"]):
        if shutil.which(argv[0]) is None:
            continue
        probe = subprocess.run(
            [*argv, "version"], capture_output=True, text=True, check=False
        )
        if probe.returncode == 0:
            return argv
    return None


_COMPOSE_ARGV = _compose_argv()
requires_compose = pytest.mark.skipif(
    _COMPOSE_ARGV is None,
    reason="needs a real docker compose binary to validate the downloaded file",
)


def _extract_tunnel_config_block(toolbox_root: Path) -> str:
    """Slice the connector-config block out of the real startup script, with the
    toolbox search root repointed at a temp directory."""
    startup = _COMPUTE_TF.read_text().split("shutdown-script", 1)[0]
    assert _TUNNEL_BLOCK_START in startup, "connector-config block not found"
    block = startup.split(_TUNNEL_BLOCK_START, 1)[1].split(_TUNNEL_BLOCK_END, 1)[0]
    # Drop the trailing comment lines that belong to the next block, then undo
    # the heredoc indentation Terraform's <<- strips at render time.
    lines = block.splitlines()
    while lines and (not lines[-1].strip() or lines[-1].lstrip().startswith("#")):
        lines.pop()
    body = textwrap.dedent("\n".join(lines))
    assert body.count(_TOOLBOX_ROOT) == 1, (
        f"expected exactly one {_TOOLBOX_ROOT} search root in the block so the "
        "harness' repoint cannot silently become a no-op"
    )
    return f"{_TUNNEL_BLOCK_START}\n{body.replace(_TOOLBOX_ROOT, str(toolbox_root))}\n"


class _BlockRun:
    """Result of executing the connector-config block."""

    def __init__(self, proc: subprocess.CompletedProcess, app_dir: Path):
        self.proc = proc
        self.app_dir = app_dir
        self.tunnel_enabled = "TUNNEL_ENABLED=1" in proc.stdout

    @property
    def output(self) -> str:
        return self.proc.stdout + self.proc.stderr

    @property
    def tunnel_file(self) -> Path:
        return self.app_dir / "docker-compose.tunnel.yml"

    @property
    def leftover_temp_files(self) -> list:
        return [
            p.name
            for p in self.app_dir.glob("docker-compose.tunnel.yml.*")
            if p.name != "docker-compose.tunnel.yml"
        ]


def _run_tunnel_block(
    tmp_path: Path,
    *,
    enabled: str = "true",
    token: str = "test-tunnel-token",
    download: str | None = None,
    stale_file: str | None = None,
    stale_toolbox_copy: str | None = None,
    silent_success: bool = False,
    write_env: bool = True,
) -> _BlockRun:
    """Execute the block with a temp $APP_DIR. ``download`` is the object GCS
    serves (None = download failure); ``silent_success`` makes the download exit
    0 without producing a file; ``stale_file`` seeds a tunnel file from a prior
    boot; ``stale_toolbox_copy`` seeds one inside the toolbox chroot under the
    fixed name a pre-#1594 boot would have used."""
    app_dir = tmp_path / "compose"
    app_dir.mkdir()
    # The real api/db compose file and a representative .env: the block must
    # leave both untouched, and `config -q` merges the base file.
    shutil.copy(_BASE_COMPOSE, app_dir / "docker-compose.yml")
    if write_env:
        (app_dir / ".env").write_text(
            "DATA_DIR=/mnt/disks/data\nIMAGE_URL=example.dev/trackrat/api:latest\n"
        )
    if stale_file is not None:
        (app_dir / "docker-compose.tunnel.yml").write_text(stale_file)

    toolbox_root = tmp_path / "toolbox"
    if stale_toolbox_copy is not None:
        chroot_dir = toolbox_root / "mnt/disks/data/compose"
        chroot_dir.mkdir(parents=True)
        (chroot_dir / "docker-compose.tunnel.yml").write_text(stale_toolbox_copy)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    toolbox = bin_dir / "toolbox"
    toolbox.write_text(_TOOLBOX_STUB)
    toolbox.chmod(0o755)
    # $COMPOSE_PATH is a single binary on the VM; forward to the real CLI here.
    compose = bin_dir / "docker-compose-shim"
    compose.write_text(f'#!/bin/bash\nexec {" ".join(_COMPOSE_ARGV)} "$@"\n')
    compose.chmod(0o755)

    source = tmp_path / "gcs-object.yml"
    if download is not None:
        source.write_text(download)

    script = (
        _extract_tunnel_config_block(toolbox_root)
        + '\necho "TUNNEL_ENABLED=$TUNNEL_ENABLED"\n'
    )
    proc = subprocess.run(
        ["bash", "-e", "-c", script],
        capture_output=True,
        text=True,
        env={
            # docker needs HOME/PATH from the real environment to find its
            # config and the CLI plugin directory.
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "APP_DIR": str(app_dir),
            "COMPOSE_PATH": str(compose),
            "DEPLOY_BUCKET": "trackrat-deploy-test",
            "ENABLE_CLOUDFLARE_TUNNEL": enabled,
            "CLOUDFLARE_TUNNEL_TOKEN": token,
            "STUB_DOWNLOAD_SOURCE": str(source),
            "STUB_SILENT_SUCCESS": "1" if silent_success else "",
            "STUB_TOOLBOX_ROOT": str(toolbox_root),
            "STUB_CALL_LOG": str(tmp_path / "calls.log"),
        },
    )
    return _BlockRun(proc, app_dir)


def _assert_api_db_config_intact(run: _BlockRun) -> None:
    """api/db startup must be independent of anything the connector block does."""
    assert run.proc.returncode == 0, (
        "the connector block must never abort the startup script (set -e is "
        f"active): {run.output}"
    )
    base = run.app_dir / "docker-compose.yml"
    assert base.read_text() == _BASE_COMPOSE.read_text(), "api/db compose was modified"
    assert (
        (run.app_dir / ".env").read_text().startswith("DATA_DIR=")
    ), ".env was modified"


@requires_compose
def test_tunnel_block_installs_only_the_validated_download(tmp_path):
    """Enabled boot + successful download installs exactly the new file."""
    served = _TUNNEL_COMPOSE.read_text()
    run = _run_tunnel_block(tmp_path, download=served, stale_file=_STALE_TUNNEL_YML)

    _assert_api_db_config_intact(run)
    assert run.tunnel_enabled, run.output
    assert run.tunnel_file.read_text() == served, (
        "the installed file must be exactly the validated download, not the "
        "stale copy from the prior boot"
    )
    assert run.leftover_temp_files == [], "download temp file was not cleaned up"


@requires_compose
def test_tunnel_block_fails_closed_when_download_fails_over_stale_file(tmp_path):
    """Enabled boot + stale file + failed download does not launch cloudflared.

    This is the reopened #1594 defect: the download error was swallowed and the
    existence check that followed could not tell a fresh file from one left on
    the persistent disk by an earlier boot.
    """
    run = _run_tunnel_block(tmp_path, download=None, stale_file=_STALE_TUNNEL_YML)

    _assert_api_db_config_intact(run)
    assert not run.tunnel_enabled, (
        "a failed download must leave the connector disabled, not fall back to "
        f"the stale file: {run.output}"
    )
    assert not run.tunnel_file.exists(), (
        "the stale connector config must be gone — the shutdown drain and the "
        "bring-up both key off file presence"
    )
    assert "download failed" in run.output, run.output
    assert run.leftover_temp_files == []


@requires_compose
def test_tunnel_block_rejects_malformed_download(tmp_path):
    """A malformed download neither replaces the last known file nor launches."""
    run = _run_tunnel_block(
        tmp_path, download=_TRUNCATED_TUNNEL_YML, stale_file=_STALE_TUNNEL_YML
    )

    _assert_api_db_config_intact(run)
    assert not run.tunnel_enabled, run.output
    assert not run.tunnel_file.exists(), (
        "the malformed download must never land at the canonical path (and the "
        "stale file it would have replaced is cleared up front)"
    )
    assert "failed validation" in run.output, run.output
    assert run.leftover_temp_files == []


@requires_compose
def test_tunnel_block_rejects_download_that_is_not_a_compose_file(tmp_path):
    """Parseable YAML that is not a compose file is still rejected — an HTML or
    JSON error page from a misconfigured bucket must not be installed."""
    run = _run_tunnel_block(tmp_path, download='{"error": "AccessDenied"}\n')

    _assert_api_db_config_intact(run)
    assert not run.tunnel_enabled, run.output
    assert not run.tunnel_file.exists()
    assert "failed validation" in run.output, run.output


@requires_compose
@pytest.mark.parametrize(
    "enabled,token,reason",
    [
        ("false", "test-tunnel-token", "flag off"),
        ("true", "", "token absent"),
    ],
)
def test_tunnel_block_removes_stale_state_when_disabled(
    tmp_path, enabled, token, reason
):
    """Disabled boot removes stale connector state and never downloads."""
    run = _run_tunnel_block(
        tmp_path, enabled=enabled, token=token, stale_file=_STALE_TUNNEL_YML
    )

    _assert_api_db_config_intact(run)
    assert (
        not run.tunnel_enabled
    ), f"{reason} must leave the connector off: {run.output}"
    assert not run.tunnel_file.exists(), f"stale state survived a {reason} boot"
    assert not (tmp_path / "calls.log").exists(), f"{reason} must not download"
    assert run.leftover_temp_files == []


@requires_compose
def test_tunnel_block_download_target_is_unique_per_boot(tmp_path):
    """The toolbox-mount lookup is a name-based `find`, so a fixed temp name
    could resolve to a copy left in the toolbox chroot by an earlier boot even
    when this boot's download failed. Two runs must use different names."""
    names = set()
    for i in range(2):
        run_dir = tmp_path / f"run{i}"
        run_dir.mkdir()
        run = _run_tunnel_block(run_dir, download=_TUNNEL_COMPOSE.read_text())
        assert run.tunnel_enabled, run.output
        log = (run_dir / "calls.log").read_text()
        names.add(log.strip().rsplit("/", 1)[-1])
    assert len(names) == 2, f"download target name must be unique per boot, got {names}"


@requires_compose
def test_tunnel_block_ignores_stale_copy_inside_the_toolbox_chroot(tmp_path):
    """The other half of the staleness problem, and why the temp name is unique.

    toolbox writes into its own chroot, so the script locates the download with
    `find <toolbox> -name <file> | head -1`. When gsutil exits 0 without
    producing anything — the swallowed-failure class this issue is about — that
    find is still reached. Against the old fixed name it matches the copy an
    earlier boot left in the chroot, and the script installs and launches it. A
    per-boot name makes the stale copy unmatchable.
    """
    run = _run_tunnel_block(
        tmp_path,
        download=_TUNNEL_COMPOSE.read_text(),
        silent_success=True,
        stale_toolbox_copy=_STALE_TUNNEL_YML,
    )

    _assert_api_db_config_intact(run)
    assert not run.tunnel_enabled, (
        "a stale copy in the toolbox chroot must not satisfy this boot's "
        f"download: {run.output}"
    )
    assert not run.tunnel_file.exists()
    assert "download failed" in run.output, run.output


@requires_compose
def test_tunnel_block_validation_depends_on_the_env_file(tmp_path):
    """Pins why the block sits *below* the .env write (and the ordering test
    above): the base compose file interpolates ${IMAGE_URL} and friends from
    .env, so `compose config` on the merged pair rejects the project outright
    when .env is absent. Run the block any earlier and validation fails on every
    boot — the connector would be permanently, silently disabled."""
    run = _run_tunnel_block(
        tmp_path, download=_TUNNEL_COMPOSE.read_text(), write_env=False
    )

    assert run.proc.returncode == 0, run.output
    assert not run.tunnel_enabled, (
        "expected the merged config to be invalid without .env — if this now "
        f"passes, the ordering guarantee is no longer load-bearing: {run.output}"
    )
    assert "failed validation" in run.output, run.output
