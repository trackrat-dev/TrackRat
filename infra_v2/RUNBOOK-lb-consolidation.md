# Runbook: LB consolidation + VM right-size + HSTS preload (production)

Phased cutover for the cost-reduction work.

**Automation model (read first):** `infra_v2/cloudbuild-terraform.yaml` runs
`terraform apply -auto-approve` on the matching workspace whenever
`infra_v2/terraform/**` changes land on a deploy branch (`main` → staging,
`production` → production). So the `terraform/` root is **never** hand-applied
here — merges *are* the applies. The destructive step (old API frontend
teardown) is therefore gated on `var.consolidate_api_lb` (default `false`),
and executing it means merging the one-line cutover PR at Phase 4 — a
deliberate act that cannot ride along on an unrelated deploy. Only the
`terraform-webpage/` root (no Cloud Build trigger) is applied by hand.

## Goal / cost impact (production, us-east4)

| Change | Before | After | ~Saving/mo |
|---|---|---|---|
| VM | t2d-standard-2 (2 vCPU / 8 GB) | e2-custom-2-4096 (2 vCPU / 4 GB) | ~$22 |
| Global forwarding rules | 4 (api :80/:443 + webpage :80/:443) | 1 (shared :443, after Phase 5) | ~$55 |

Measured basis: prod CPU 24h mean 35% / peak 54% of 2 vCPU (keep 2 vCPU);
RAM 1.09 GB used of 7.76 GB (cut to 4 GB). LB egress 0.46 GB/day → the LB bill
is essentially the per-rule minimum, so the win is rule count, not data.

> **Verify the ~$55 before committing to Phase 5.** The estimate assumes
> forwarding rules bill per-rule (~$18/mo each). Under GCP's legacy
> first-5-rules bundle pricing, 4 → 1 rules in this project saves far less
> (possibly $0 if the project's total rule count stays ≤ 5 either way).
> Check the actual invoice line item ("Forwarding Rule Minimum Service
> Charge") before deciding the HSTS-preload lock-in is worth it; the
> consolidation through Phase 4 is worth doing regardless.

## How the change is split (two PRs)

**PR 1 — prep (safe to merge anytime; auto-applies are non-destructive):**

- `infra_v2/terraform/variables.tf` — `machine_type` default → `e2-custom-2-4096`;
  new `consolidate_api_lb` bool (default **false**).
- `infra_v2/terraform/main.tf` — local
  `create_api_frontend = !(var.environment == "production" && var.consolidate_api_lb)`
  → true everywhere until the cutover PR flips the variable.
- `infra_v2/terraform/loadbalancer.tf` — keeps backend service + cert; gates the
  HTTPS frontend on `create_api_frontend`; `moved` blocks map the seven existing
  frontend resources to their new `[0]` addresses (plan must show **0 destroys**
  while the gate is off).
- `infra_v2/terraform/outputs.tf` — `load_balancer_ip` guarded.
- `infra_v2/terraform-webpage/main.tf` — production URL map host-routes
  `apiv2.trackrat.net` → API backend service; proxy serves the API cert via SNI;
  webpage bucket emits HSTS (`preload`). Hand-applied at Phase 1.
- `backend_v2/src/trackrat/main.py` (+ `tests/test_hsts_middleware.py`) — HSTS
  header on HTTPS API responses.

Merging PR 1 to `main` / pushing to `production` rolls each VM to E2 (template
replace + MIG roll, ~5 min blip) and no-ops the frontend (moves only). That is
the *only* infra effect until Phase 4.

**PR 2 — cutover (merge only at Phase 4):** one line, `consolidate_api_lb`
default `false` → `true`. Merging it to `production` is what tears down the old
API frontend. Committing the flip (rather than a hand-run `-var`) keeps every
subsequent auto-apply consistent — nothing later recreates the frontend.

## Key facts

- Shared IP after cutover: **136.110.151.144** (`trackrat-webpage-production-ip`).
- Released after cutover: **34.102.163.196** (`trackrat-production-ip`).
- API backend service name (looked up by the webpage root): `trackrat-production-backend`.
- Both managed certs (`trackrat-production-cert`, `trackrat-webpage-production-cert`)
  are already ACTIVE — we attach both to the shared proxy, so there is **no cert
  provisioning gap** at cutover.
- DNS is in Cloudflare, **grey-cloud / DNS-only** (do not enable the orange proxy).

## Ordering rule (do not violate)

`terraform-webpage` apply (Phase 1) is **additive** and safe anytime.
Merging the cutover PR to `production` (Phase 4) **deletes the old API frontend
+ IP** via the auto-apply and must happen **only after** apiv2 DNS has moved
and the old API forwarding rule has drained to ~0 req. Merging it before the
DNS flip will break apiv2 — recovery gets a *different* IP (see Rollback).

---

## Phase 0 — Merge PR 1: HSTS header + VM right-size + gated (no-op) frontend refactor

The backend must already emit HSTS before we advertise preload.

1. Merge PR 1 to `main`. The staging auto-apply fires: expect the staging VM to
   roll to E2 and the seven frontend resources to show **moved** (not
   destroyed/recreated) in the Cloud Build plan output. Verify staging:
   ```bash
   dig +short staging.apiv2.trackrat.net    # unchanged IP = the moves worked
   curl -sI https://staging.apiv2.trackrat.net/health | grep -i strict-transport-security
   bash scripts/validate-staging.sh
   ```
2. Push to `production`. This rolls the production VM to E2 (**~5 min apiv2
   blip** while the MIG recreates the single VM — same as any deploy; schedule
   accordingly) and no-ops the frontend. Verify:
   ```bash
   curl -sI https://apiv2.trackrat.net/health | grep -i strict-transport-security
   # expect: strict-transport-security: max-age=31536000; includeSubDomains; preload

   # VM is now e2 — confirm memory headroom on the smaller box:
   curl -s https://apiv2.trackrat.net/admin/stats.json | python3 -c 'import sys,json;m=json.load(sys.stdin)["system"]["memory"];print(m)'
   #   watch used_gb stays well under 4 GB total; if it climbs toward the cap,
   #   bump machine_type to e2-custom-2-6144 and redeploy.
   ```

**Watch for a few days before proceeding:** E2 is oversubscribed vs T2D's
dedicated cores; at 35% avg there's headroom, but confirm p99 latency and CPU
haven't regressed, and that the reduced-DB working set keeps RAM under 4 GB.
The VM change is now decoupled from the LB cutover, so a `machine_type` revert
is just another deploy.

## Phase 1 — Build the consolidated LB (additive; apiv2 DNS unchanged)

```bash
cd infra_v2/terraform-webpage
terraform init
terraform plan -var="project_id=trackrat-v2"    # review: url-map host rule, proxy 2nd cert, bucket header
terraform apply -var="project_id=trackrat-v2"
```

Validate the shared LB serves all three hosts **before** touching DNS (force the
new IP with `--resolve`):

```bash
# API via the shared LB
curl -s --resolve apiv2.trackrat.net:443:136.110.151.144 https://apiv2.trackrat.net/health/ready
# Webpage apex + www still fine, now with HSTS
curl -sI --resolve trackrat.net:443:136.110.151.144 https://trackrat.net/ | grep -i strict-transport
curl -sI --resolve www.trackrat.net:443:136.110.151.144 https://www.trackrat.net/ | grep -iE 'HTTP/|strict-transport'
```

All three must succeed with a valid cert (SNI picks the right one). If the API
check fails, do **not** proceed — check the `data.google_compute_backend_service.api_production`
lookup resolved and the API cert self-link is correct.

## Phase 2 — Flip apiv2 DNS to the shared IP

In Cloudflare, change the `apiv2` A record:

```
apiv2.trackrat.net  A  34.102.163.196  ->  136.110.151.144   (DNS only / grey)
```

Validate after TTL:

```bash
dig +short apiv2.trackrat.net           # expect 136.110.151.144
curl -sI https://apiv2.trackrat.net/health/ready | head -1
bash ../../scripts/validate-staging.sh https://apiv2.trackrat.net   # or the prod e2e checks
```

## Phase 3 — Confirm the old API LB has drained

The old frontend (34.102.163.196) still exists at this point. Wait until it sees
~0 requests before tearing it down (adjust window as needed):

```bash
# From repo root, using the same GCP creds as gcp-logs.py — request_count for the
# old API forwarding rule should fall to ~0 over the last ~15 min.
gcloud monitoring time-series list \
  --filter='metric.type="loadbalancing.googleapis.com/https/request_count" AND resource.labels.forwarding_rule_name="trackrat-production-https"' \
  --format='value(points.value.int64Value)' 2>/dev/null | head
```

(Or read it via the Monitoring REST API as in the investigation.) Proceed once it
is effectively zero — remaining hits are non-preloaded stragglers/scanners that
will fail closed, which is acceptable per the port-80 decision.

## Phase 4 — Merge PR 2: tear down the old API frontend

> Merging the cutover PR (`consolidate_api_lb` default → `true`) to
> `production` triggers the auto-apply that destroys the old API frontend.
> Do **not** merge it until Phases 1–3 are done. The VM was already resized in
> Phase 0, so this phase touches only the frontend — no MIG roll, no blip
> (apiv2 traffic is already on the shared LB).

1. Merge PR 2 to `main` first. The staging auto-apply must be a **no-op**
   (staging keeps its frontend regardless of the variable) — confirm the Cloud
   Build plan shows `0 to add, 0 to change, 0 to destroy`.
2. Push to `production`. In the Cloud Build plan output expect
   **DESTROY**: global address, url map, https/http proxies, 2 forwarding
   rules, redirect url map. Expect **NO CHANGE**: backend service, managed ssl
   cert (still attached to the shared proxy), health check, instance template.

Validate:

```bash
curl -sI https://apiv2.trackrat.net/health/ready | head -1        # 200 via shared LB
curl -sI https://apiv2.trackrat.net/health | grep -i strict-transport
gcloud compute forwarding-rules list --global --format='table(name,IPAddress,portRange)'
#   apiv2 rules gone; remaining: webpage :80 + :443 (+ any staging).
```

## Phase 5 — HSTS preload, then drop port 80 (the last rule)

Do **not** drop :80 until the domain is confirmed on the preload list — the
submission checker wants the working http→https redirect, and non-browser http
clients rely on it until preload propagates.

1. Confirm HSTS on apex + www + apiv2 over HTTPS (all carry `preload`, above).
2. Submit `trackrat.net` at https://hstspreload.org/ (requires `includeSubDomains`
   + `preload`, which the config already sends). **This is a multi-year, hard-to-
   reverse commitment: every current and future `*.trackrat.net` subdomain must
   stay HTTPS-only in browsers — including `staging.apiv2` / `staging.trackrat.net`.**
3. Wait for status to reach "preloaded" and for it to ship in browser stable
   releases (weeks). Keep :80 up throughout.
4. Only then, remove the port-80 frontend in `infra_v2/terraform-webpage/main.tf`
   (a follow-up commit) and apply:
   - `google_compute_global_forwarding_rule.webpage_production_http`
   - `google_compute_target_http_proxy.webpage_production_http_proxy`
   - `google_compute_url_map.webpage_production_https_redirect`
   ```bash
   cd infra_v2/terraform-webpage && terraform apply -var="project_id=trackrat-v2"
   ```
   Result: **1** production global forwarding rule (shared :443).

## Rollback

- **Phase 1**: `terraform destroy` the added resources, or revert the url-map to a
  plain `default_service` and drop the 2nd cert / bucket header. apiv2 unaffected
  (DNS never moved).
- **Phase 2**: revert the apiv2 A record to `34.102.163.196` (old API LB still live).
- **Phase 4** (frontend torn down): recovery is `git revert` of the cutover PR
  pushed to `production` — the auto-apply recreates the API IP/proxies/rules —
  then point apiv2 DNS back. The **new IP will differ** from 34.102.163.196 —
  cutover again via DNS. Prefer fixing forward on the shared LB.
- **VM**: set `machine_type` back to `t2d-standard-2` and deploy (another MIG roll).
- **Phase 5 / preload**: effectively irreversible on browser timescales — serve
  `max-age=0` and request removal at hstspreload.org, expect months. This is why
  :80 stays until preload is certain.
