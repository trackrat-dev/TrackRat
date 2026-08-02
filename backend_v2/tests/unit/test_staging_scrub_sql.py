"""
Pins the staging PII scrub to a single source of truth (issue #1710).

Two independent things scrub a cloned staging database:

  1. The boot-time scrub in ``infra_v2/terraform/compute.tf``, which runs
     before the API container starts. This is the copy that actually keeps
     staging from pushing to production users' phones.
  2. The manual backstop ``scripts/scrub-staging-db.sh``, used for local or
     hand-managed database work.

They used to carry duplicate hand-written TRUNCATE lists. They agreed, but
nothing kept them agreeing, and a future PII-bearing table added to only the
script would silently not be scrubbed on the VM. Both now read
``scripts/scrub-staging-db.sql``; these tests fail if either one re-inlines
its own list.

Reads the real repo files, no mocks — same approach as
``test_cloudflare_tunnel_isolation.py``.
"""

import re
from pathlib import Path

from trackrat.models.database import Base

# backend_v2/tests/unit/<this file> -> backend_v2 is parents[2], repo root parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]

_SCRUB_SQL = _REPO_ROOT / "scripts" / "scrub-staging-db.sql"
_SCRUB_SH = _REPO_ROOT / "scripts" / "scrub-staging-db.sh"
_COMPUTE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "compute.tf"

# The tables that must never quietly drop off the scrub list. Adding a table to
# scrub-staging-db.sql is fine and needs no change here; removing one of these
# is the dangerous direction and fails.
_REQUIRED_TABLES = {
    "device_tokens",
    "live_activity_tokens",
    "cached_api_responses",
    "scheduler_task_runs",
}


def _strip_sql_comments(sql: str) -> str:
    """Drop ``--`` line comments so only executable statements remain."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def _truncated_tables(sql: str) -> list[str]:
    """Table names targeted by TRUNCATE statements, in file order."""
    return re.findall(
        r"\bTRUNCATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)",
        _strip_sql_comments(sql),
        re.IGNORECASE,
    )


def test_scrub_sql_file_exists_and_truncates_the_pii_tables():
    """The single source of truth still covers every table that leaks to users."""
    assert _SCRUB_SQL.is_file(), f"expected scrub SQL at {_SCRUB_SQL}"

    tables = _truncated_tables(_SCRUB_SQL.read_text())
    missing = _REQUIRED_TABLES - set(tables)

    assert not missing, (
        f"scrub-staging-db.sql no longer truncates {sorted(missing)}. Every "
        "table here is scrubbed on staging boot; dropping one means a cloned "
        f"production disk keeps that data. Found: {tables}"
    )
    assert len(tables) == len(set(tables)), f"duplicate TRUNCATE targets: {tables}"


def test_scrub_sql_cascades_device_tokens():
    """device_tokens must CASCADE — subscriptions/preferences reference it.

    route_alert_subscriptions.device_id and route_preferences.device_id are
    ON DELETE CASCADE foreign keys, so a bare TRUNCATE would fail outright and
    (under compute.tf's ``set -e``) abort the VM boot.
    """
    sql = _strip_sql_comments(_SCRUB_SQL.read_text())

    match = re.search(
        r"\bTRUNCATE\s+TABLE\s+device_tokens\b([^;]*);", sql, re.IGNORECASE
    )
    assert match is not None, "no TRUNCATE TABLE device_tokens statement found"
    assert "cascade" in match.group(1).lower(), (
        "TRUNCATE TABLE device_tokens must specify CASCADE; without it the "
        "statement errors on the referencing foreign keys and staging boot fails"
    )


def test_scrub_sql_targets_only_real_tables():
    """A typo'd table name aborts the staging VM boot, so catch it here."""
    known = set(Base.metadata.tables)
    unknown = [t for t in _truncated_tables(_SCRUB_SQL.read_text()) if t not in known]

    assert not unknown, (
        f"scrub-staging-db.sql truncates unknown table(s) {unknown}. The boot "
        "scrub runs under 'set -e', so an unresolvable table name takes the "
        "whole staging instance down rather than just skipping the scrub."
    )


def test_scrub_sql_contains_only_truncate_statements():
    """The file is executed verbatim on boot — keep it to TRUNCATE only."""
    statements = [
        s.strip()
        for s in _strip_sql_comments(_SCRUB_SQL.read_text()).split(";")
        if s.strip()
    ]

    assert statements, "scrub-staging-db.sql has no executable statements"
    offenders = [s for s in statements if not re.match(r"(?i)^TRUNCATE\s+TABLE\b", s)]
    assert not offenders, (
        f"non-TRUNCATE statement(s) in scrub-staging-db.sql: {offenders}. This "
        "file is run as-is against the staging database at boot."
    )


def test_scrub_sql_is_safe_inside_a_double_quoted_shell_string():
    """compute.tf interpolates this file into psql -c "..." in a bash script.

    A double quote, dollar sign, backtick or backslash would terminate or
    re-interpret that string and break the staging VM's startup script.
    """
    text = _SCRUB_SQL.read_text()
    forbidden = {
        '"': "double quote",
        "$": "dollar sign",
        "`": "backtick",
        "\\": "backslash",
    }

    found = sorted(name for ch, name in forbidden.items() if ch in text)
    assert not found, (
        f"scrub-staging-db.sql contains {found}. It is embedded into a "
        'double-quoted shell string (psql -c "...") in compute.tf\'s startup '
        "script, so these characters break the staging VM boot."
    )


def test_compute_tf_embeds_the_shared_sql_and_inlines_no_table_list():
    """The boot scrub must read the shared file, not its own copy."""
    text = _COMPUTE_TF.read_text()

    assert '${file("${path.module}/../../scripts/scrub-staging-db.sql")}' in text, (
        "compute.tf no longer embeds scripts/scrub-staging-db.sql. The boot "
        "scrub is the copy that protects production users; it must not carry "
        "a private table list (issue #1710)."
    )
    assert "TRUNCATE" not in text.upper(), (
        "compute.tf has an inline TRUNCATE again — that is exactly the "
        "duplication issue #1710 removed. Add tables to "
        "scripts/scrub-staging-db.sql instead."
    )


def test_scrub_script_reads_the_shared_sql_and_inlines_no_table_list():
    """The manual backstop must read the same file as the boot scrub."""
    text = _SCRUB_SH.read_text()

    assert "scrub-staging-db.sql" in text, (
        "scripts/scrub-staging-db.sh no longer reads scrub-staging-db.sql, so "
        "it can drift from the boot scrub in compute.tf (issue #1710)."
    )
    assert "TRUNCATE" not in text.upper(), (
        "scripts/scrub-staging-db.sh has an inline TRUNCATE again. Add tables "
        "to scripts/scrub-staging-db.sql instead."
    )
