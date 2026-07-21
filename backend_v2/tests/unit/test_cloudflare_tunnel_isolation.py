"""Regression guards for the Cloudflare Tunnel connector isolation (issue #1578).

The 2026-07-19 staging outage happened because the ``cloudflared`` connector was
(a) gated on *secret existence* rather than a committed flag, and (b) shared the
``api``/``db`` compose file, so a bad connector token/config aborted the whole
``compose up``. The remediation:

* the connector lives in a **separate** ``docker-compose.tunnel.yml`` that the
  api/db bring-up never loads (parse-level isolation);
* it is brought up in a **second, non-fatal** ``up`` only when the committed
  ``enable_cloudflare_tunnel`` flag is true AND the token secret is present.

These tests pin those invariants to the actual repo files so a future edit that
re-couples the connector to api/db — or reverts to secret-only gating — fails
loudly instead of silently re-arming the outage. They parse the real files (no
mocks), matching how the deploy pipeline and startup script consume them.
"""

from pathlib import Path

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


def test_enable_cloudflare_tunnel_variable_defaults_off():
    text = _VARIABLES_TF.read_text()
    assert 'variable "enable_cloudflare_tunnel"' in text
    # The block must default to false (committed-off).
    block = text.split('variable "enable_cloudflare_tunnel"', 1)[1].split(
        "variable ", 1
    )[0]
    assert (
        "default     = false" in block
    ), "connector must ship off by default (issue #1578)"


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


def test_startup_script_removes_tunnel_file_when_disabled():
    """File presence must mean "tunnel enabled this boot". $APP_DIR lives on the
    persistent data disk (staging's is cloned from production's on every deploy),
    so without cleanup a tunnel file from a prior enabled boot lingers and the
    shutdown drain would merge a stale file on disabled boots (issue #1594)."""
    text = _COMPUTE_TF.read_text()
    assert 'rm -f "$APP_DIR/docker-compose.tunnel.yml"' in text, (
        "disabled boots must remove any stale docker-compose.tunnel.yml so "
        "file presence tracks the enable flag"
    )
    # The cleanup must live in the startup script's disabled branch, before the
    # shutdown script (which relies on the invariant).
    startup = text.split("shutdown-script", 1)[0]
    assert 'rm -f "$APP_DIR/docker-compose.tunnel.yml"' in startup


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
