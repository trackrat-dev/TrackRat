"""Regression guard for the deploy bucket's lifecycle rule (issue #1823).

``google_storage_bucket.deploy`` is not an archive of build artifacts — it is the
**bootstrap source for the MIG**. The instance startup script downloads
``docker-compose.yml`` and ``docker-compose.tunnel.yml`` from it on *every* boot
(``infra_v2/terraform/compute.tf``), so whatever lives there is load-bearing for
the ability of the infrastructure to rebuild itself.

The original rule deleted every object older than 30 days with no ``with_state``
qualifier, which in GCS means the **live** generation too, not just superseded
ones. Going ~30 days without a production deploy therefore silently aged out the
live bootstrap artifacts. Nothing broke at deletion time, because a *running* VM
had already copied the compose file to the persistent data disk — so the failure
stayed invisible until the next instance recreate, which then could not boot at
all:

    === Downloading docker-compose.yml ===
    CommandException: No URLs matched: gs://trackrat-v2-deploy-production/docker-compose.yml

That is the 33-minute production outage on 2026-09-20. The infrastructure had
been unable to rebuild itself for 12 days before anyone found out, and the
re-upload that resolved it restarted the same 30-day clock.

These tests pin the rule to noncurrent generations against the real file, so a
future edit that drops ``with_state`` — re-arming a failure whose first symptom
is a total outage weeks later — fails here instead of in production.
"""

import re
from pathlib import Path

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_STORAGE_TF = _REPO_ROOT / "infra_v2" / "terraform" / "storage.tf"


def _resource_block(source: str, resource_type: str, name: str) -> str:
    """Return the body of a single Terraform resource block, brace-matched.

    A regex alone cannot do this safely — ``lifecycle_rule``/``condition``/
    ``action`` are nested blocks, so the first ``}`` is not the end of the
    resource. Counting braces keeps the assertions below scoped to the deploy
    bucket rather than accidentally matching a neighbouring resource.
    """
    header = f'resource "{resource_type}" "{name}" {{'
    start = source.find(header)
    assert start != -1, f"{resource_type}.{name} not found in {_STORAGE_TF}"

    depth = 0
    for index in range(start + len(header) - 1, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start + len(header) : index]
    raise AssertionError(f"unbalanced braces in {resource_type}.{name}")


def _deploy_bucket() -> str:
    return _resource_block(_STORAGE_TF.read_text(), "google_storage_bucket", "deploy")


def test_deploy_bucket_lifecycle_rule_is_scoped_to_archived_generations():
    """The live bootstrap artifacts must never be a deletion candidate."""
    body = _deploy_bucket()
    assert "lifecycle_rule" in body, (
        "google_storage_bucket.deploy has no lifecycle_rule at all — if the rule "
        "was removed rather than scoped, say so explicitly here; this test is "
        "the record that its scoping is deliberate (issue #1823)."
    )

    condition = re.search(r"condition\s*\{(.*?)\}", body, re.DOTALL)
    assert condition is not None, "lifecycle_rule has no condition block"
    condition_body = condition.group(1)

    assert re.search(r'with_state\s*=\s*"ARCHIVED"', condition_body), (
        'the deploy bucket\'s lifecycle rule must carry with_state = "ARCHIVED". '
        "Without it GCS applies the age condition to the LIVE generation, which "
        "deletes the docker-compose.yml the startup script boots from and leaves "
        "the MIG unable to rebuild an instance (issue #1823, 2026-09-20 outage). "
        f"Condition block was:\n{condition_body}"
    )


def test_deploy_bucket_versioning_is_enabled():
    """An ARCHIVED-scoped rule only garbage-collects anything if generations are
    actually retained. Without versioning there are no noncurrent objects, so
    the rule silently becomes a no-op and stale generations accumulate forever —
    a different bug, but one introduced by 'fixing' this one carelessly."""
    body = _deploy_bucket()
    versioning = re.search(r"versioning\s*\{(.*?)\}", body, re.DOTALL)
    assert versioning is not None, (
        "google_storage_bucket.deploy must keep versioning — the ARCHIVED-scoped "
        "lifecycle rule depends on noncurrent generations existing (issue #1823)"
    )
    assert re.search(r"enabled\s*=\s*true", versioning.group(1)), (
        "versioning must be enabled = true for the ARCHIVED lifecycle rule to "
        "have anything to collect"
    )


def test_deploy_bucket_has_no_unscoped_delete_rule():
    """Belt and braces: catch a *second* rule being added later that deletes on
    age alone. The first test would still pass — it only inspects the first
    condition block — while the live object became deletable again."""
    body = _deploy_bucket()
    rules = re.findall(r"lifecycle_rule\s*\{(.*?)\n  \}", body, re.DOTALL)
    assert rules, "expected at least one lifecycle_rule block to inspect"

    for rule in rules:
        if not re.search(r'type\s*=\s*"Delete"', rule):
            continue  # SetStorageClass and friends are not destructive here
        assert re.search(r'with_state\s*=\s*"ARCHIVED"', rule), (
            "every Delete lifecycle rule on the deploy bucket must be scoped to "
            "ARCHIVED generations, or it can remove the live bootstrap artifacts "
            f"the MIG boots from (issue #1823). Offending rule:\n{rule}"
        )
