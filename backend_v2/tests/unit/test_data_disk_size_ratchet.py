"""`var.disk_size_gb` is a one-way ratchet (issue #1828).

``google_compute_disk.data`` is the PostgreSQL data disk. GCP cannot shrink a
persistent disk, and the google provider responds to a *decrease* by forcing
**replacement** rather than by failing the plan — so lowering this number does
not produce a tidy error, it produces a plan that destroys and recreates the
production database disk.

That is measured, not assumed. Against the real provider (hashicorp/google
v5.45.2) with ``terraform plan -refresh=false`` over a state holding
``size = 50``::

    50 -> 40    # google_compute_disk.data must be replaced
                ~ size = 50 -> 40 # forces replacement
                Plan: 1 to add, 0 to change, 1 to destroy.
    50 -> 60    # google_compute_disk.data will be updated in-place
    50 -> 50    No changes.

Nothing else stands in the way:

* ``google_compute_disk.data`` has no ``prevent_destroy``; its ``lifecycle``
  block ignores only ``snapshot`` (``infra_v2/terraform/storage.tf``);
* ``infra_v2/terraform/`` is auto-applied by the ``trackrat-terraform-production``
  Cloud Build trigger, which has **no path filter**, so it runs on every push to
  the ``production`` branch — not only on infrastructure changes.

The drift that prompted this: the production disk was grown 40 -> 50 GB out of
band on 2026-09-20 during incident response while the variable still declared
40, leaving a pending shrink queued behind the next production promotion.

The guard keeps the declared size and the recorded provisioned size in lockstep
rather than asserting a floor. A floor was the first attempt and it was not
actually a ratchet: growing the disk by editing only ``variables.tf`` satisfies
``declared >= 50`` without ever advancing the recorded value, so the guard stays
pinned at 50 and a later reduction from 60 down to anything in 50..59 passes the
very test written to stop it. Requiring both to move together costs one extra
line when the disk genuinely grows, and in exchange the ratchet tracks reality
instead of a stale high-water mark.

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
#
# This is asserted EQUAL to the declared size, not as a floor. A floor
# (`declared >= 50`) looked like a ratchet but was not one: growing the disk to
# 60 by editing only variables.tf would satisfy it without ever advancing this
# constant, leaving the guard pinned at 50 — so a later reduction from 60 down
# to anything in 50..59 would sail through the very test written to stop it.
# Requiring the two to move together means a growth must record itself here, in
# the same commit, and the ratchet tracks reality instead of a stale high-water
# mark.
_PROVISIONED_DISK_SIZE_GB = 50


def _declared_disk_size() -> int:
    block = re.search(
        r'variable\s+"disk_size_gb"\s*\{(.*?)\n\}', _VARIABLES_TF.read_text(), re.DOTALL
    )
    assert block, f'variable "disk_size_gb" not found in {_VARIABLES_TF}'
    default = re.search(r"default\s*=\s*(\d+)", block.group(1))
    assert default, "disk_size_gb has no numeric default"
    return int(default.group(1))


def test_declared_disk_size_matches_the_recorded_provisioned_size():
    """The regression, and the ratchet that prevents it recurring.

    Verified empirically against the real provider (hashicorp/google v5.45.2,
    `terraform plan -refresh=false` over a state holding size = 50):

        50 -> 40   # google_compute_disk.data must be replaced
                   ~ size = 50 -> 40 # forces replacement
                   Plan: 1 to add, 0 to change, 1 to destroy.
        50 -> 60   # google_compute_disk.data will be updated in-place
        50 -> 50   No changes.

    So a shrink is not an apply that fails safely — it is a destroy and
    recreate of the PostgreSQL data disk, on a resource with no
    prevent_destroy, in a root auto-applied on every push to production.
    """
    declared = _declared_disk_size()
    assert declared == _PROVISIONED_DISK_SIZE_GB, (
        f"var.disk_size_gb is {declared} GB but _PROVISIONED_DISK_SIZE_GB "
        f"records {_PROVISIONED_DISK_SIZE_GB} GB.\n\n"
        f"If {declared} < {_PROVISIONED_DISK_SIZE_GB}: this is a shrink. GCP "
        "cannot shrink a persistent disk and the provider forces REPLACEMENT, "
        "so the next apply plans to destroy and recreate the PostgreSQL data "
        "disk (issue #1828).\n\n"
        f"If {declared} > {_PROVISIONED_DISK_SIZE_GB}: this is a growth, which "
        "is fine and applies in place — but _PROVISIONED_DISK_SIZE_GB must be "
        "raised to match in the SAME commit. Leaving it behind would pin the "
        "ratchet to a stale value and let a later shrink down to that value "
        "pass unnoticed."
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
    body = lifecycle.group(1)

    # Terraform accepts a bare `ignore_changes = all` as well as a bracketed
    # list. Checking only the list form would let the broadest possible version
    # of this mistake through: `all` silences `size` too, and a guard that
    # early-returns on it passes while claiming to protect the disk.
    assert re.search(r"ignore_changes\s*=\s*all\b", body) is None, (
        "google_compute_disk.data uses `ignore_changes = all`, which silences "
        "`size` along with everything else — Terraform would stop reconciling "
        "disk drift entirely while this guard reported green (issue #1828)"
    )

    ignore = re.search(r"ignore_changes\s*=\s*\[(.*?)\]", body, re.DOTALL)
    if ignore is None:
        return
    ignored = {
        entry.strip().strip('"')
        for entry in ignore.group(1).split(",")
        if entry.strip()
    }
    assert "size" not in ignored, (
        "google_compute_disk.data ignores changes to `size`, which hides disk "
        "drift rather than fixing it and defeats this guard (issue #1828)"
    )
