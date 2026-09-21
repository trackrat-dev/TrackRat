"""`var.disk_size_gb` is a one-way ratchet (issue #1828).

``google_compute_disk.data`` is the PostgreSQL data disk. GCP cannot shrink a
persistent disk, and the google provider (pinned ``~> 5.0``) responds to a
*decrease* by forcing **replacement** rather than by failing the plan — so
lowering this number does not produce a tidy error, it produces a plan that
destroys and recreates the production database disk.

Nothing else stands in the way:

* ``google_compute_disk.data`` has no ``prevent_destroy``; its ``lifecycle``
  block ignores only ``snapshot`` (``infra_v2/terraform/storage.tf``);
* ``infra_v2/terraform/`` is auto-applied by the ``trackrat-terraform-production``
  Cloud Build trigger, which has **no path filter**, so it runs on every push to
  the ``production`` branch — not only on infrastructure changes.

The drift that prompted this: the production disk was grown 40 -> 50 GB out of
band on 2026-09-20 during incident response while the variable still declared
40, leaving a pending shrink queued behind the next production promotion.

This test encodes the ratchet rather than pinning an exact number, so growing
the disk later stays a one-line change while shrinking it — the dangerous
direction — has to get past a failure that explains why.

A snapshot schedule exists (``infra_v2/terraform/backup.tf``), so the worst case
is a restore rather than permanent loss. That is still an outage, and not
something to discover from a plan output during an unrelated deploy.
"""

import re
from pathlib import Path

# backend_v2/tests/unit/<this file> -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TERRAFORM_DIR = _REPO_ROOT / "infra_v2" / "terraform"
_VARIABLES_TF = _TERRAFORM_DIR / "variables.tf"
_STORAGE_TF = _TERRAFORM_DIR / "storage.tf"

# What production actually has provisioned, as of the 2026-09-20 out-of-band
# growth. Raise this only alongside a real disk growth; never lower it.
_PROVISIONED_DISK_SIZE_GB = 50


def _declared_disk_size() -> int:
    block = re.search(
        r'variable\s+"disk_size_gb"\s*\{(.*?)\n\}', _VARIABLES_TF.read_text(), re.DOTALL
    )
    assert block, f'variable "disk_size_gb" not found in {_VARIABLES_TF}'
    default = re.search(r"default\s*=\s*(\d+)", block.group(1))
    assert default, "disk_size_gb has no numeric default"
    return int(default.group(1))


def test_declared_disk_size_is_not_a_shrink_of_the_provisioned_disk():
    """The regression: a declared value below what is provisioned queues a
    destroy-and-recreate of the Postgres data disk behind the next apply."""
    declared = _declared_disk_size()
    assert declared >= _PROVISIONED_DISK_SIZE_GB, (
        f"var.disk_size_gb is {declared} GB but the production data disk is "
        f"{_PROVISIONED_DISK_SIZE_GB} GB. GCP cannot shrink a persistent disk, "
        "and the provider forces REPLACEMENT on a shrink — so the next apply "
        "(which fires on every push to the production branch, the terraform "
        "trigger has no path filter) plans to destroy and recreate the "
        "PostgreSQL data disk. If the disk genuinely shrank, update "
        "_PROVISIONED_DISK_SIZE_GB deliberately and say why (issue #1828)."
    )


def test_data_disk_still_consumes_the_shared_variable():
    """The assertion above is only meaningful while the disk reads this
    variable. A per-workspace override or a hardcoded size would leave the
    guard passing against a value nothing uses."""
    storage = _STORAGE_TF.read_text()
    disk = re.search(
        r'resource\s+"google_compute_disk"\s+"data"\s*\{(.*?)\n\}', storage, re.DOTALL
    )
    assert disk, "google_compute_disk.data not found"
    assert re.search(r"size\s*=\s*var\.disk_size_gb", disk.group(1)), (
        "google_compute_disk.data no longer sizes itself from var.disk_size_gb, "
        "so the ratchet guard above no longer protects it (issue #1828). "
        f"Block was:\n{disk.group(1)}"
    )


def test_data_disk_does_not_ignore_size_changes():
    """`ignore_changes = [size]` would silence the drift instead of resolving
    it — the plan goes quiet while Terraform's state and reality stay divergent,
    which is strictly worse than the noisy version: the next person to remove it
    inherits the shrink."""
    storage = _STORAGE_TF.read_text()
    disk = re.search(
        r'resource\s+"google_compute_disk"\s+"data"\s*\{(.*?)\n\}', storage, re.DOTALL
    )
    assert disk, "google_compute_disk.data not found"
    lifecycle = re.search(r"lifecycle\s*\{(.*?)\}", disk.group(1), re.DOTALL)
    if lifecycle is None:
        return  # no lifecycle block at all is fine
    ignore = re.search(r"ignore_changes\s*=\s*\[(.*?)\]", lifecycle.group(1), re.DOTALL)
    if ignore is None:
        return
    ignored = {entry.strip() for entry in ignore.group(1).split(",") if entry.strip()}
    assert "size" not in ignored, (
        "google_compute_disk.data ignores changes to `size`, which hides disk "
        "drift rather than fixing it and defeats this guard (issue #1828)"
    )
