# Runbook: Enable or disable a transit data source per environment

## Why

`TRACKRAT_DISABLED_DATA_SOURCES` fully turns a data source off in the backend —
real-time collection, schedule generation, GTFS refresh, service-alert polling,
and API serving (`backend_v2/src/trackrat/settings.py`,
`services/scheduler.py`, `services/departure.py::active_data_sources`,
`api/utils.py::ensure_source_enabled`).

Until issue #1634 this was a **single hardcoded literal** in the startup script
(`infra_v2/terraform/compute.tf`), rendered identically into both the `staging`
and `production` workspaces. That made the staging soak that gates every
re-enablement unsafe to run: dropping a source from the literal to soak it in
staging also armed the **next production apply** — including an unrelated,
push-triggered one — to enable it in production. Since
`infra_v2/cloudbuild-terraform.yaml` auto-applies this root on every
deploy-branch push, that apply could happen at any time and without review.

The value is now a per-environment map (`var.disabled_data_sources`), resolved
for the current workspace by `local.disabled_data_sources` in `main.tf`. Staging
and production diverge deliberately and visibly in version control.

## Rules

1. **Change the committed default, never `-var`.** `cloudbuild-terraform.yaml`
   passes only `environment` and `project_id`; every other value comes from the
   committed default. A `-var` override applied by hand is silently reverted by
   the next push to a deploy branch. This matches the existing discipline on
   `consolidate_api_lb`, `frontend_via_cloudflare`, and
   `enable_cloudflare_tunnel`.
2. **A source is enabled by its absence.** Codes must match `ALL_DATA_SOURCES`
   in the backend. `settings.py` ignores an unrecognized code rather than
   erroring, so a typo silently **enables** a source. The variable's regex
   validation catches casing mistakes; it cannot catch a misspelling of a real
   code. Confirm against `/health` after every apply (step 4 below).
3. **Enable the backend before the clients.** iOS
   (`TrainSystem.disabledSystems`) and web (`DISABLED_SYSTEMS` in
   `webpage_v2/src/data/stations.ts`) mirror this set by hand. Removing a system
   there while the backend still has it disabled ships a picker entry that
   returns nothing.
4. **Applying restarts the API.** The MIG's `update_policy` is `PROACTIVE` /
   `REPLACE` with `max_surge_fixed = 0` and `max_unavailable_fixed = 1`, so the
   changed startup script replaces the single instance in place. Expect a short
   API outage per environment. Apply outside peak hours.

## Procedure

### 1. Edit the committed default

`infra_v2/terraform/variables.tf`, `variable "disabled_data_sources"`. Change
**only the environment you intend to move**:

```hcl
default = {
  # SEPTA soak: enabled in staging only (issue #1634). Production stays dark
  # until the staging gates pass.
  staging    = ["BART", "WMATA", "MBTA", "METRA"]
  production = ["BART", "WMATA", "MBTA", "METRA", "SEPTA_RR", "SEPTA_METRO"]
}
```

### 2. Verify the render before applying

Confirms the diff is what you meant and that the other environment is untouched:

```bash
cd infra_v2/terraform
terraform fmt -check && terraform validate

terraform workspace select staging
terraform plan -var="environment=staging" -var="project_id=trackrat-v2" \
  | grep -A2 TRACKRAT_DISABLED_DATA_SOURCES

terraform workspace select production
terraform plan -var="environment=production" -var="project_id=trackrat-v2" \
  | grep -A2 TRACKRAT_DISABLED_DATA_SOURCES
```

The workspace you did **not** intend to change must show no diff on that line.
A plan that touches the instance template in both workspaces means the edit
landed in the wrong place — stop and re-read the map.

### 3. Apply

```bash
terraform workspace select staging
terraform apply -var="environment=staging" -var="project_id=trackrat-v2"
```

Merging to a deploy branch applies the same change automatically; a manual
apply is only for getting there sooner. Either way the instance is replaced —
wait for the MIG to report the new instance healthy before validating.

### 4. Confirm the live set

`/health` reports the resolved sets. This is the authoritative check that the
codes parsed as intended:

```bash
curl -s https://staging.apiv2.trackrat.net/health \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data_sources'])"
```

`active` must now contain the source; `disabled` must not. If the source is
still in `disabled`, the code did not match `ALL_DATA_SOURCES` — check spelling
against `backend_v2/src/trackrat/services/departure.py`.

Then run the validation suite for the environment:

```bash
bash scripts/validate-staging.sh --ground-truth --coverage
```

### 5. Rollback

Re-add the code to that environment's list, commit, and apply. Rollback is
symmetric and takes effect on the next instance replacement.

**Collected data is not removed by the flag.** Journeys gathered while the
source was enabled stay in the database and age out under
`TRACKRAT_RETENTION_DAYS`; `active_data_sources()` and `ensure_source_enabled()`
stop them being served immediately, so a rollback needs no data cleanup. Do not
delete rows as part of a rollback — a re-enable would otherwise start from an
empty history and lose the analytics baseline the soak built up.

## Current state

| Environment | Disabled sources |
|---|---|
| staging | BART, WMATA, MBTA, METRA, SEPTA_RR, SEPTA_METRO |
| production | BART, WMATA, MBTA, METRA, SEPTA_RR, SEPTA_METRO |

Both match the pre-#1634 literal exactly; this change is mechanism-only, with
no behavior change on the first apply beyond the instance replacement.
