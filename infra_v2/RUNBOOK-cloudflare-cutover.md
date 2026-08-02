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
- **Static site** (`trackrat.net`, `www`) → **Cloudflare Pages**, replacing the
  GCS buckets. The original design here — front the bucket with Cloudflare via
  host/path transform rules — **is not implementable on our plan** and was
  withdrawn: overriding the `Host` header (required so GCS routes to the right
  bucket) is Enterprise-only on Origin Rules, and URL Rewrite explicitly
  "cannot rewrite the hostname". See issue #1713.

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
**`trackrat.net` and `www` lose it** unless Cloudflare emits it.

**Checked 2026-08-02: `trackrat.net` is NOT on the preload list.**
`https://hstspreload.org/api/v2/status?domain=trackrat.net` returns
`"status": "unknown"`, so the header was emitted but never submitted. The code
comment overstates the constraint: there is no live commitment to honour. The
header is reproduced anyway — browsers that have seen it hold it for a year,
and `webpage_v2/public/_headers` makes it free — but it is no longer a gate on
P6.

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
  The connector config itself **fails closed** (issue #1594): the stale tunnel
  file is removed before any download attempt, the download lands in a unique
  temp file that is validated with `compose config -q` and only then `mv`d into
  place. A failed or malformed download therefore leaves the connector off for
  that boot — grep `/var/log/startup.log` for `WARN: tunnel enabled but` — rather
  than launching the definition a previous boot left on the persistent disk.
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

### S8. Rehearse Phase 3 — `staging.trackrat.net` on Cloudflare Pages

Supersedes the withdrawn transform-rule design (issue #1713). Note the ordering
here is no longer a precondition for S9: S9 already merged (`89b6d94`), so
`staging.trackrat.net` is **already down** — this step restores it rather than
pre-empting an outage.

**One-time setup, before merging the pipeline change** (a build that runs
without these fails):

1. Cloudflare → Workers & Pages → create project `trackrat-webpage-staging`,
   **Direct Upload**, production branch **`main`**. (Direct Upload is a
   one-way door: a project created this way can never be switched to Git
   integration.)
2. Create an API token with the **Cloudflare Pages: Edit** account permission.
   Note the account ID.
3. Store both in Secret Manager and grant the Cloud Build service account
   (`trackrat-staging@trackrat-v2.iam.gserviceaccount.com` — both webpage
   triggers run as it) `roles/secretmanager.secretAccessor` on each:

```bash
printf '%s' '<TOKEN>' | gcloud secrets create cloudflare-pages-api-token \
  --project=trackrat-v2 --replication-policy=automatic --data-file=-
printf '%s' '<ACCOUNT_ID>' | gcloud secrets create cloudflare-account-id \
  --project=trackrat-v2 --replication-policy=automatic --data-file=-

for s in cloudflare-pages-api-token cloudflare-account-id; do
  gcloud secrets add-iam-policy-binding "$s" --project=trackrat-v2 \
    --member=serviceAccount:trackrat-staging@trackrat-v2.iam.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor
done
```

4. Check the zone for Cache Rules or Page Rules covering `*.trackrat.net`.
   Cloudflare warns that custom-domain caching can serve stale assets past a
   deploy and can pre-empt Pages routing.

**Then:** merge the pipeline change to `main`. The trigger builds and runs
`wrangler pages deploy`. Attach `staging.trackrat.net` under the project's
Custom domains tab — the zone is on Cloudflare, so the DNS record is created
automatically and there is no old record to remove.

**Verify — this is the P5 rehearsal, so do all of it.** The asset check is the
one that matters most: it is what proves no catch-all is shadowing real files.

```bash
BASE=https://staging.trackrat.net
curl -sS -o /dev/null -w '%{http_code}\n' $BASE/                      # 200
curl -sS -o /dev/null -w '%{http_code}\n' $BASE/trains/TR/NY          # SPA fallback
curl -sS -o /dev/null -w '%{http_code}\n' $BASE/train/3515/TR/NY      # shared-link shape

# A hashed asset must be itself, NOT the HTML shell.
ASSET=$(curl -sS $BASE/ | grep -o '/assets/index-[^"]*\.js' | head -1)
curl -sSI $BASE$ASSET | grep -iE 'content-type|cache-control'   # text/javascript + immutable

curl -sSI $BASE/ | grep -iE 'strict-transport|cache-control'    # HSTS + no-store
curl -sSI $BASE/sw.js | grep -i cache-control                   # no-store
curl -sSI $BASE/.well-known/apple-app-site-association | grep -i content-type
curl -sS  $BASE/.well-known/apple-app-site-association | python3 -m json.tool >/dev/null \
  && echo "AASA ok"
```

Two behaviours are **not** documented by Cloudflare and must be observed here
rather than assumed:

- **The SPA fallback's status code.** Pages falls back to the app shell for
  unmatched paths whenever a deployment has no top-level `404.html`, but does
  not document whether that is a 200. Today's GCS behaviour is 404-with-body,
  so anything is at least a tie — but do not claim the improvement without
  seeing it.
- **Whether `.well-known/` uploads at all.** It is a dot-directory. There is no
  documented Pages exclusion for hidden files, but if wrangler skips it,
  Universal Links break with no error anywhere. The AASA checks above are the
  only place this surfaces.

Also load the site in a browser: the service worker should register, and API
calls should go to `https://staging-api.trackrat.net/api/v2` (#1712).

**Rollback:** the GCS bucket `trackrat-webpage-staging` still holds the last
pre-migration build, but nothing serves it — the staging LB is gone. Rollback
is therefore forward-only: fix and redeploy to Pages. This is acceptable
precisely because staging is already dark.

**After a ≥24h soak:** delete `google_storage_bucket.webpage_staging`, its IAM
member, and the `staging_webpage_bucket` output from
`infra_v2/terraform-webpage/main.tf`, then apply that root manually.

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

### P5. Static site on Cloudflare Pages

Same shape as S8 against `trackrat-webpage-production`, but production is live,
so the order below matters. `infra_v2/cloudbuild-webpage.yaml` deploys to
**both** GCS and Pages on purpose: it removes the window where one destination
is serving while the other goes stale. Do not delete the GCS steps early.

1. Create the Pages project `trackrat-webpage-production`, **Direct Upload**,
   production branch **`production`**. Reuses the S8 secrets — no new token.
2. Populate and inspect it before any DNS moves:
   ```bash
   export CLOUDFLARE_API_TOKEN=$(gcloud secrets versions access latest \
     --secret=cloudflare-pages-api-token --project=trackrat-v2)
   export CLOUDFLARE_ACCOUNT_ID=$(gcloud secrets versions access latest \
     --secret=cloudflare-account-id --project=trackrat-v2)
   ./scripts/deploy-webpage.sh production
   ```
   Run the full S8 verification block against the project's `*.pages.dev` URL.
   `trackrat.net` is untouched at this point.
3. Merge `main` → `production` so the dual-deploy pipeline is live. Confirm one
   push writes to both destinations.
4. Attach `trackrat.net` and `www.trackrat.net` as custom domains on the Pages
   project. **This is the cutover** — it repoints the apex away from
   `136.110.151.144`. Re-run the S8 verification block against
   `https://trackrat.net` and `https://www.trackrat.net`.
5. **Soak ≥24h.** Then delete the `sync`, `cache-html` and `cache-assets` steps
   and the `_WEBPAGE_BUCKET` substitution from `cloudbuild-webpage.yaml`.

Universal links are worth a real check here, not just a curl: Apple's CDN
caches the AASA file, so an installed app may keep working for a while off the
old copy. Confirm a shared `/train/...` link still opens the app.

**Rollback (before step 5):** remove the custom domains from the Pages project
and recreate the grey `A` records pointing at `136.110.151.144`. The GCS bucket
is still receiving every build, so it is current, not stale — that is the whole
reason for the dual deploy. After step 5 the bucket goes stale immediately and
rollback means restoring those pipeline steps and pushing.

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

Removable: the API backend service (`loadbalancer.tf`) and
`trackrat-production-cert`. Both are dead once nothing routes through a Google
LB. They are free to keep and serve as a rollback path — leave them a week, then
remove. Fold the two out-of-band secret IAM grants into `secrets.tf` at that
point (the note in that file anticipates this).

**Must keep — do not delete with the load balancer:**

| Resource | Why it outlives the LB |
|---|---|
| `google_compute_health_check.trackrat` | Also drives `google_compute_instance_group_manager.trackrat.auto_healing_policies`, not just the backend service |
| `google_compute_firewall.allow_health_checks` (`network.tf:5`) | Auto-healing probes come from `130.211.0.0/22` + `35.191.0.0/16` on port 8000 — the same ranges the LB used |

The health check has two consumers: the backend service in `loadbalancer.tf`
(dies with the cutover) and the MIG's `auto_healing_policies` in `compute.tf`
(does not). Deleting it
leaves the production MIG unable to replace a wedged instance, and the failure is
**silent** — nothing breaks at deletion time; you find out the next time an
instance needs auto-healing and doesn't get it. Neither resource is `count`-gated,
so nothing in Terraform protects against removing them by hand in the console.
This matches the invariant already stated for the staging rehearsal in S9.

---

## Rollback matrix

| Step | Rollback | Cost |
|---|---|---|
| S3–S6 | none needed (tunnel is additive) | — |
| S7 | recreate grey `A` → staging LB IP | seconds |
| S8 | forward-only — fix and redeploy to Pages (staging LB is already gone) | minutes |
| S9 | `git revert` + re-apply | new IP, DNS update |
| P1–P3 | none needed (connector additive) | — |
| P4 | grey `A` `apiv2` → `136.110.151.144` | seconds |
| P5 | detach Pages custom domains, recreate grey `A` → `136.110.151.144` (GCS stays current while the pipeline dual-deploys) | seconds |
| **P6** | **re-apply webpage LB Terraform** | **new IP + DNS + cert reprovision** |

## Verification cheatsheet

```bash
# Global forwarding rules currently billed (goal: empty after P6)
gcloud compute forwarding-rules list --global --project=trackrat-v2

# Connector health (the Cloudflare dashboard is authoritative; app-side check:)
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env staging --search cloudflared

# End-to-end via Cloudflare (expect cf-ray + server: cloudflare)
curl -sSI https://staging-api.trackrat.net/health/ready
bash scripts/validate-staging.sh
bash scripts/e2e-api-test.sh https://apiv2.trackrat.net --no-random

# Static site on Pages: the shell, a deep link, and — the one that catches a
# catch-all redirect shadowing real files — a hashed asset served as itself.
BASE=https://staging.trackrat.net   # or https://trackrat.net after P5
curl -sS -o /dev/null -w '%{http_code}\n' $BASE/trains/TR/NY
ASSET=$(curl -sS $BASE/ | grep -o '/assets/index-[^"]*\.js' | head -1)
curl -sSI $BASE$ASSET | grep -i content-type          # text/javascript, NOT text/html
curl -sSI $BASE/.well-known/apple-app-site-association | grep -i content-type

# Confirm the CUD-covered VM size is untouched by any of this
gcloud compute instances list --project=trackrat-v2 \
  --format="table(name,machineType.basename(),status)"
```
