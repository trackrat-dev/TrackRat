# Runbook: Eliminate the global forwarding-rule minimum charge (Cloudflare cutover)

> **Status as of 2026-07-28.** Rewritten after a full state audit; the previous
> revision (2026-07-21) was stale in four places — see
> "What changed since the last revision" before executing.

## Why

The `Cloud Load Balancer Forwarding Rule Minimum Global` SKU bills a **flat
$0.025/hr (~$0.60/day, ~$219/yr) for the first 5 global forwarding rules,
aggregated per project** — not per rule and not per load balancer. Reducing the
rule *count* (the `RUNBOOK-lb-consolidation.md` work: 6 → 4 → 1) does **not**
lower this SKU at all — it stays $0.60/day until the project has **zero** global
forwarding rules.

Switching to a regional or passthrough load balancer does not help either:
regional forwarding rules have their own identical minimum, and forwarding-rule
billing is the same across all LB types. The only way to $0 is to stop using a
Google-managed load balancer entirely.

Corollary worth remembering while executing: because the minimum is flat for the
first 5 rules, **recreating staging (which adds 2 forwarding rules) costs $0
extra on this SKU**. There is no cost pressure to rush the pilot.

`driverat-v0` sits on the same billing account and has its own global forwarding
rule (`driverat-staging-https`), which bills its own separate minimum. It is
explicitly **out of scope here** — the same procedure gets applied there once
this lands in `trackrat-v2`.

## Target architecture

Front everything with Cloudflare (DNS is already there) and delete both Google
load balancers:

- **APIs** (`apiv2`, `staging.apiv2`) → **Cloudflare Tunnel** (`cloudflared`
  container in the isolated `backend_v2/docker-compose.tunnel.yml`). Cloudflare
  terminates TLS at its edge and routes the hostname to `http://api:8000` over
  the private Docker network. The VM needs no public ingress, no origin
  certificate, and no reverse proxy — the origin stays exactly as it is today
  (plain HTTP on `:8000`).
- **Static site** (`trackrat.net`, `www`) → keep the GCS bucket, front it with
  Cloudflare (orange-cloud) via host/path transform rules. (Decision: keep the
  existing GCS deploy pipeline rather than migrating to Pages.)

End state: no `google_compute_*_forwarding_rule` anywhere → SKU $0. Also sheds
the webpage backend-bucket/CDN, two managed SSL certs, url maps, and the API's
static IPs.

---

## What changed since the last revision

These findings invalidate parts of the 2026-07-21 procedure. Read them before
executing.

### 1. Staging rebuilds itself on the next push to `main`

```
trackrat-terraform-staging  → branch ^main$   (NO includedFiles filter)
trackrat-staging-deploy     → branch ^main$   (NO includedFiles filter)
```

Neither trigger has a path filter, so they fire on **every** push to `main`, not
only on `infra_v2/terraform/**` changes (the previous revision claimed the
latter — that was wrong). And the staging workspace state was never destroyed:
`gs://trackrat-v2-terraform-state/terraform/state/staging.tfstate` still holds
48 resource blocks / 54 instances (serial 404) pointing at resources that were
deleted out-of-band on 2026-07-24. Staging has stayed down only because `main`
has not moved since `c09bdd4`.

Consequences:

- **Recreating staging needs no special procedure** — any push to `main` does it.
- **Merging *any* PR to `main` recreates staging**, including a docs-only PR.
- **The final teardown must disable those two triggers**, or staging returns on
  the next main push forever (step P7).

### 2. Staging's database is auto-seeded from production

`cloudbuild-staging.yaml::prepare-staging-disk` snapshots
`trackrat-production-data` and rebuilds `trackrat-staging-data` from it. Good
news — no empty-DB problem, and `validate-staging.sh` works immediately — but it
does land **production PII in staging**. That is handled automatically; running
`scripts/scrub-staging-db.sh` by hand is **not** a required step (issue #1710).

Two layers close it, both on every boot:

1. **Boot-time scrub** — `infra_v2/terraform/compute.tf`, guarded on
   `$ENVIRONMENT = staging`. It starts *only* the `db` container, waits for
   `pg_isready`, truncates the tables listed in `scripts/scrub-staging-db.sql`,
   and only then brings up the API — so the API never sees production
   notification data. It runs under `set -e`, so if the scrub cannot run the
   API container is never started at all.
2. **Startup guard** — `_check_staging_notification_safety` in
   `backend_v2/src/trackrat/main.py` disables APNS outright if either token
   table still looks like a production clone, or if the counts cannot be read.

`scripts/scrub-staging-db.sh` is a **backstop for local or hand-managed database
work**. It reads the same `scrub-staging-db.sql` as the boot scrub, so the two
cannot drift. Step S5 is therefore an optional verification, not a mandatory
action.

The pipeline also already has an `upload-compose-tunnel` step that ships
`docker-compose.tunnel.yml` to the VM.

### 3. The staging pilot cannot rehearse Phase 4

Staging drops its LB via `frontend_via_cloudflare`. Production's last forwarding
rule lives in `infra_v2/terraform-webpage/`, a **separate Terraform root with no
Cloud Build trigger at all**. Phase 4 is therefore a hand-edit plus a manual
local `terraform apply`, and it is the one step the pilot does not de-risk.

Related: `frontend_via_cloudflare` is already a **no-op for production**.
`main.tf` computes

```hcl
create_api_frontend = !var.frontend_via_cloudflare && !(var.environment == "production" && var.consolidate_api_lb)
```

and `consolidate_api_lb = true`, so production's `create_api_frontend` is
already `false`. The variable's description overstates its effect: it removes
the charge on **staging** only.

### 4. Deleting the webpage LB silently drops an HSTS preload commitment

`google_compute_backend_bucket.webpage_production_backend` emits

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

via `custom_response_headers`, and the code comment calls it "a standing
commitment — do not remove it while the domain is on the preload list." That
header source dies with the LB in Phase 4. `apiv2` is unaffected (FastAPI
middleware sets the same header — verified in live response headers), but
**`trackrat.net` and `www` lose it** unless Cloudflare emits it. Confirm the
domain's status at https://hstspreload.org first; if it is genuinely preloaded,
the Cloudflare transform rules **must** add this header before P6.

### Also corrected

- `trackrat-cloudflare-tunnel-token-staging` **no longer exists** (it went with
  the 2026-07-24 teardown). Use `gcloud secrets create`, not `versions add`.
  The previous revision's warning about a stale invalid token is obsolete.
- The `production` branch **does** now carry the full tunnel code
  (`docker-compose.tunnel.yml`, the `--no-deps` / `--remove-orphans` hardening,
  and the `enable_cloudflare_tunnel` gate), and the production instance template
  was rebuilt from it on 2026-07-26. The old "Phase 2 step 0: promote first"
  precondition is **already satisfied**.

---

## Current state (2026-07-28)

| | value |
|---|---|
| Global forwarding rules in `trackrat-v2` | **1** — `trackrat-webpage-production-https` (443) |
| Shared LB IP | `136.110.151.144` |
| Routing | url map host-routes `apiv2.trackrat.net` → API backend service; everything else → GCS backend bucket |
| `consolidate_api_lb` | `true` on both branches (applied) |
| `frontend_via_cloudflare` | `false` on both branches |
| `enable_cloudflare_tunnel` | `false` on both branches |
| Cloudflare | zone on `april`/`leland.ns.cloudflare.com`; `trackrat.net`, `www`, `apiv2` all **grey-cloud** → `136.110.151.144`. Nothing proxied. |
| Staging | fully deleted from GCP; tfstate stale (finding 1); DNS still points at the dead `136.69.90.77` |
| Tunnel secrets | none exist |

Phases complete: **0 of 4.** (The LB consolidation was a different runbook.)

## Repo levers

- `infra_v2/terraform/variables.tf` — **`enable_cloudflare_tunnel`** (default
  `false`). Master on/off switch for the connector. `cloudflared` starts **only**
  when this flag is `true` **and** the token secret is present (issue #1578).
- `infra_v2/terraform/variables.tf` — **`frontend_via_cloudflare`** (default
  `false`). Tears down *this workspace's* dedicated API frontend. Effective on
  staging; already a no-op on production (finding 3).
- `backend_v2/docker-compose.tunnel.yml` — the `cloudflared` service, isolated
  from `docker-compose.yml` so a malformed config or an invalid token cannot
  abort the API.
- `infra_v2/terraform/compute.tf` — startup script reads
  `trackrat-cloudflare-tunnel-token-$ENVIRONMENT` from Secret Manager, brings
  `db`/`api` up from `docker-compose.yml` alone, then starts `cloudflared` in a
  separate **non-fatal** `up -d --no-deps cloudflared` (issue #1594). The
  shutdown script drains the connector first so Cloudflare's edge deregisters
  the instance before the API goes away.
- `infra_v2/terraform/secrets.tf` — a NOTE only; the tunnel-token secrets and
  their IAM grants stay out-of-band during the cutover.

Both flags are **shared committed defaults** across workspaces
(`cloudbuild-terraform.yaml` passes only `environment` and `project_id`).
Flipping them on `main` arms staging; merging `main` → `production` arms
production, gated only by the production secret's existence. That is by design —
just be deliberate about when the production secret gets created.

---

# Part A — Staging pilot

Two pushes to `main`. The tunnel and secret are created **before** the first
push, so the staging rebuild and the connector land together. A throwaway
hostname keeps the tunnel and the LB independently testable, so a bad token
never leaves you without a working staging to debug against.

### S1. Create the staging tunnel (Cloudflare dashboard)

Zero Trust → Networks → Tunnels → **Create a tunnel** → *Cloudflared*, name
`trackrat-staging`. Copy the **tunnel token** (the long value in the
`--token ...` install command).

Add public hostname **`staging-tunnel.trackrat.net`** → `HTTP` → `api:8000`.
Use the throwaway hostname only — do **not** add `staging.apiv2` yet.

### S2. Store the token and grant the VM read access

The secret no longer exists — this is a `create`, not a `versions add`.

```bash
printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets create trackrat-cloudflare-tunnel-token-staging \
  --project=trackrat-v2 --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding trackrat-cloudflare-tunnel-token-staging \
  --project=trackrat-v2 \
  --member="serviceAccount:trackrat-staging@trackrat-v2.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

The grant stays out of Terraform so the repo state remains inert: the startup
script reads the secret tolerantly, so a missing secret just leaves the tunnel
off.

### S3. Push #1 — rebuild staging *with* the connector

PR to `main`: in `infra_v2/terraform/variables.tf`, set
`enable_cloudflare_tunnel` default `false` → `true`. Merge.

This single push rebuilds all of staging (Terraform sees ~30 resources missing,
per finding 1) **and** boots `cloudflared`. If the token is bad the connector
crash-loops, but `api`/`db` are unaffected — that isolation is the point of
#1578/#1594.

```bash
gcloud builds list --project=trackrat-v2 --region=us-east4 --limit=5 \
  --format="table(id.slice(0,8),createTime,status,substitutions._ENVIRONMENT)"

gcloud compute instances list --project=trackrat-v2
```

Expect a `trackrat-staging-*` instance. Allow ~15 min for terraform + deploy +
boot.

### S4. Repoint staging DNS at the new LB (control path)

Staging's records still point at the dead `136.69.90.77`. Get the new IP and
update both **grey** `A` records (`staging.apiv2.trackrat.net`,
`staging.trackrat.net`):

```bash
gcloud compute forwarding-rules list --global --project=trackrat-v2 \
  --format="table(name,IPAddress,portRange)"
```

The managed cert sits in `PROVISIONING` until DNS propagates (15–60 min). This
gives you a working non-Cloudflare staging to compare against.

### S5. Confirm the PII scrub ran (optional verification — finding 2)

The scrub is automatic on every staging boot; this only confirms it. Expect
zero rows, and `staging_notification_safety_ok` in the logs.

```bash
bash scripts/scrub-staging-db.sh --dry-run

PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py \
  --env staging --search staging_notification_safety
```

Only run the script without `--dry-run` if those show production data still
present — that would mean the boot scrub failed and is worth investigating,
not just papering over.

### S6. Verify both paths independently

```bash
# connector came up
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env staging --search cloudflared

# tunnel path — expect 200 + cf-ray + server: cloudflare
curl -sSI https://staging-tunnel.trackrat.net/health/ready

# LB path — the control
curl -sSI https://staging.apiv2.trackrat.net/health/ready
bash scripts/validate-staging.sh
```

**Do not proceed** until the tunnel path returns 200 with `cf-ray`.

**Rollback:** nothing to undo — the tunnel is additive and `staging.apiv2` is
still served by the LB.

### S7. Cut `staging.apiv2` over to the tunnel

Add `staging.apiv2.trackrat.net` as a public hostname on the tunnel (this
creates the proxied record), then delete the grey `A` record.

```bash
curl -sSI https://staging.apiv2.trackrat.net/health/ready     # expect cf-ray
bash scripts/validate-staging.sh
```

**Rollback:** recreate the grey `A` record pointing at the staging LB IP.

### S8. Rehearse Phase 3 — `staging.trackrat.net` via Cloudflare → GCS

Orange-cloud the record. Transform Rules: rewrite `Host` →
`storage.googleapis.com` and path → `/trackrat-webpage-staging<path>`; map `/`
and extensionless paths to `…/index.html` so client-side routing and the SPA
entrypoint resolve. Preserve the bucket's own `Cache-Control` (keep Cloudflare's
cache respecting origin).

**Add the HSTS response header here** (finding 4) so the production rule is
already proven:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

Verify the homepage, a deep link, and `/.well-known/apple-app-site-association`
(must stay `application/json`).

**Rollback:** grey-cloud back to the staging LB IP.

### S9. Push #2 — tear down the staging LB

PR to `main`: set `frontend_via_cloudflare` default `false` → `true`. Merge.

The plan should destroy **exactly**: `google_compute_global_address.trackrat[0]`,
`google_compute_url_map.trackrat[0]` (+ redirect), both target proxies, both
`google_compute_global_forwarding_rule.trackrat_*[0]`, and the
`serve_webpage_on_api_lb` host-route — and nothing else. The backend service,
MIG, health check, and cert stay.

```bash
gcloud compute forwarding-rules list --global --project=trackrat-v2
# expect ONLY trackrat-webpage-production-https

bash scripts/validate-staging.sh
curl -sSI https://staging.trackrat.net
```

**Rollback:** `git revert` the flip and re-apply (new IP — update DNS to match).

Staging is now fully Cloudflare-fronted with zero Google LB. That validates
everything except the cross-root Phase 4 delete.

---

# Part B — Production

### P0. Fix observability first (blocking)

`scripts/server-usage.py::fetch_lb_logs` queries only
`resource.type="http_load_balancer"`. Once `apiv2` rides the tunnel it no longer
traverses the GCP HTTP LB, so the usage report and the daily-report routine will
**silently show zero API traffic** while users are active. Add a post-cutover
traffic source — Cloudflare Logpush / GraphQL Analytics, or the backend's own
request stats / `cos_containers` app logs — and merge to `main` before P4.

Client-IP attribution already works: `api/utils.get_client_ip` reads
`CF-Connecting-IP`.

### P1. Merge `main` → `production`

Before pushing, confirm the merge did not revert the VM sizing (the `production`
branch carries `t2d-standard-1`; `main` still defaults to `t2d-standard-2` with
a staging ternary):

```bash
git show production:infra_v2/terraform/variables.tf | grep -A4 'variable "machine_type"'   # expect t2d-standard-1
git show production:infra_v2/terraform/main.tf | grep -n machine_type                      # expect NO staging ternary
```

The production apply rolls a new instance template carrying the tunnel-enabled
startup script. The connector stays **off** — no production secret exists yet.
`frontend_via_cloudflare = true` arriving with the merge changes nothing for
production (finding 3). Verify:

```bash
gcloud compute forwarding-rules list --global --project=trackrat-v2   # unchanged
curl -sSI https://apiv2.trackrat.net/health/ready                      # 200, server: uvicorn
```

### P2. Create the production tunnel and secret

Tunnel `trackrat-production`, public hostname **`apiv2-tunnel.trackrat.net`** →
`HTTP` → `api:8000`.

```bash
printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets create trackrat-cloudflare-tunnel-token-production \
  --project=trackrat-v2 --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding trackrat-cloudflare-tunnel-token-production \
  --project=trackrat-v2 \
  --member="serviceAccount:trackrat-production@trackrat-v2.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### P3. Redeploy production so the VM picks up the secret

Push to `production`, or:

```bash
gcloud compute instance-groups managed rolling-action restart trackrat-production-mig \
  --project=trackrat-v2 --zone=us-east4-a
```

Production restarts reboot the *same* instance and preserve Docker container
state, which is exactly why the `--remove-orphans` startup script had to land
first (P1).

```bash
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env production --search cloudflared
curl -sSI https://apiv2-tunnel.trackrat.net/health/ready
```

`apiv2` is still on the LB at this point — zero user impact.

### P4. Cut `apiv2` over to the tunnel

Add `apiv2.trackrat.net` as a tunnel public hostname; delete the grey `A` record.

```bash
curl -sSI https://apiv2.trackrat.net/health/ready      # expect cf-ray
bash scripts/e2e-api-test.sh https://apiv2.trackrat.net --no-random
```

**Soak ≥24h.** Confirm the P0 usage report still reports traffic.

**Rollback:** grey `A` → `136.110.151.144` (the webpage LB still host-routes
`apiv2`).

### P5. Static site behind Cloudflare

Orange-cloud `trackrat.net` and `www.trackrat.net`; same transform rules as S8
but against `trackrat-webpage-production`, **including the HSTS header**
(finding 4). Verify deep links, AASA content-type, and:

```bash
curl -sSI https://trackrat.net | grep -i strict-transport-security
```

**Rollback:** grey-cloud back to `136.110.151.144`.

### P6. Phase 4 — delete the webpage LB (point of no easy return)

Edit `infra_v2/terraform-webpage/main.tf` and remove:

- both `google_compute_global_forwarding_rule.webpage_production_*`
- both target proxies (`webpage_production_proxy`, `webpage_production_http_proxy`)
- both url maps (`webpage_production`, `webpage_production_https_redirect`)
- `google_compute_backend_bucket.webpage_production_backend`
- `google_compute_managed_ssl_certificate.webpage_production_cert`
- `google_compute_global_address.webpage_production_ip`
- `data "google_compute_backend_service" "api_production"`
- the `production_webpage_ip` output

Keep both GCS buckets and the webpage Cloud Build triggers.

No trigger exists for this root — apply it manually:

```bash
cd infra_v2/terraform-webpage
terraform init
terraform plan      # review carefully: must destroy only the LB resources
terraform apply

gcloud compute forwarding-rules list --global --project=trackrat-v2   # expect EMPTY
```

Do this only after P4 and P5 have been stable ≥24h. It deletes the shared IP;
rollback means re-applying with a new IP and repointing DNS.

The SKU drops to $0 on the next billing cycle.

### P7. Destroy staging durably

```bash
cd infra_v2/terraform
terraform init && terraform workspace select staging
terraform destroy -var="environment=staging" -var="project_id=trackrat-v2"
```

Then **disable `trackrat-terraform-staging` and `trackrat-staging-deploy`**
(Cloud Build → Triggers, region `us-east4` → Disable). Without this, finding 1
guarantees staging returns on the next `main` push. A `--disabled` flag on
`gcloud builds triggers update` was not confirmed for the installed gcloud
version — use the console unless you verify it.

Also: delete the staging DNS records, delete
`trackrat-cloudflare-tunnel-token-staging`, and delete the `trackrat-staging`
tunnel in Cloudflare.

### P8. Cleanup (optional, ~1 week later)

The API backend service, its health check, and `trackrat-production-cert` are
dead once nothing routes through a Google LB. They are free to keep and serve as
a rollback path — leave them a week, then remove. Fold the two out-of-band
secret IAM grants into `secrets.tf` at that point (the note in that file
anticipates this).

---

## Rollback matrix

| Step | Rollback | Cost |
|---|---|---|
| S3–S6 | none needed (tunnel is additive) | — |
| S7 | recreate grey `A` → staging LB IP | seconds |
| S8 | grey-cloud `staging.trackrat.net` | seconds |
| S9 | `git revert` + re-apply | new IP, DNS update |
| P1–P3 | none needed (connector additive) | — |
| P4 | grey `A` `apiv2` → `136.110.151.144` | seconds |
| P5 | grey-cloud `trackrat.net` + `www` | seconds |
| **P6** | **re-apply webpage LB Terraform** | **new IP + DNS + cert reprovision** |

## Verification cheatsheet

```bash
# Global forwarding rules currently billed (goal: empty after P6)
gcloud compute forwarding-rules list --global --project=trackrat-v2

# Connector health (the Cloudflare dashboard is authoritative; app-side check:)
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env staging --search cloudflared

# End-to-end via Cloudflare (expect cf-ray + server: cloudflare)
curl -sSI https://staging.apiv2.trackrat.net/health/ready
bash scripts/validate-staging.sh
bash scripts/e2e-api-test.sh https://apiv2.trackrat.net --no-random

# Confirm the CUD-covered VM size is untouched by any of this
gcloud compute instances list --project=trackrat-v2 \
  --format="table(name,machineType.basename(),status)"
```
