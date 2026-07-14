# Runbook: LB consolidation + VM right-size + HSTS preload (production)

Manual cutover for the cost-reduction work. **Nothing here is applied
automatically** — run each step by hand and gate on the validation checks.

## Goal / cost impact (production, us-east4)

| Change | Before | After | ~Saving/mo |
|---|---|---|---|
| VM | t2d-standard-2 (2 vCPU / 8 GB) | e2-custom-2-4096 (2 vCPU / 4 GB) | ~$22 |
| Global forwarding rules | 4 (api :80/:443 + webpage :80/:443) | 1 (shared :443, after Phase 5) | ~$55 |

Measured basis: prod CPU 24h mean 35% / peak 54% of 2 vCPU (keep 2 vCPU);
RAM 1.09 GB used of 7.76 GB (cut to 4 GB). LB egress 0.46 GB/day → the LB bill
is essentially the per-rule minimum, so the win is rule count, not data.

## What the PR changes

- `infra_v2/terraform/variables.tf` — `machine_type` default → `e2-custom-2-4096`.
- `infra_v2/terraform/main.tf` — new local `create_api_frontend` (false in prod).
- `infra_v2/terraform/loadbalancer.tf` — keeps backend service + cert; **gates the
  HTTPS frontend on `create_api_frontend`** (prod no longer owns IP/url-map/proxies/rules).
- `infra_v2/terraform/outputs.tf` — `load_balancer_ip` guarded for prod.
- `infra_v2/terraform-webpage/main.tf` — production URL map host-routes
  `apiv2.trackrat.net` → API backend service; proxy serves the API cert via SNI;
  webpage bucket emits HSTS (`preload`).
- `backend_v2/src/trackrat/main.py` (+ `tests/test_hsts_middleware.py`) — HSTS
  header on HTTPS API responses.

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
The `terraform/` production apply (Phase 4) **deletes the old API frontend + IP**
and must run **only after** apiv2 DNS has moved and the old API forwarding rule
has drained to ~0 req. Applying `terraform/` prod before the DNS flip will break
apiv2.

---

## Phase 0 — Ship the API HSTS header

The backend must already emit HSTS before we advertise preload.

1. Merge the backend change; deploy to production (push to `production` branch → CI).
2. Verify:
   ```bash
   curl -sI https://apiv2.trackrat.net/health | grep -i strict-transport-security
   # expect: strict-transport-security: max-age=31536000; includeSubDomains; preload
   ```

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

## Phase 4 — Tear down the old API frontend + resize the VM

> This single `terraform/` production apply does **two** things:
> (a) removes the old API IP/url-map/proxies/forwarding rules, and
> (b) replaces the instance (t2d → e2-custom-2-4096) → **~5 min apiv2 blip**
> while the MIG recreates the single VM (same as any deploy). Schedule a window.
> If you want them decoupled, apply the machine-type change on its own first
> (e.g. `-target=google_compute_instance_template.trackrat -target=google_compute_instance_group_manager.trackrat`)
> **only after** Phase 2, since a full `terraform/` prod apply also deletes the frontend.

```bash
cd infra_v2/terraform
terraform init
terraform workspace select production
terraform plan -var="environment=production"
#   Expect DESTROY: global address, url_map, https/http proxies, 2 forwarding
#   rules, redirect url_map. Expect REPLACE: instance template (+ MIG roll).
#   Expect NO CHANGE: backend service, managed ssl cert, health check.
terraform apply -var="environment=production"
```

Validate:

```bash
curl -sI https://apiv2.trackrat.net/health/ready | head -1        # 200 via shared LB
curl -sI https://apiv2.trackrat.net/health | grep -i strict-transport
# VM is now e2 — confirm memory headroom on the smaller box after a few minutes:
curl -s https://apiv2.trackrat.net/admin/stats.json | python3 -c 'import sys,json;m=json.load(sys.stdin)["system"]["memory"];print(m)'
#   watch used_gb stays well under 4 GB total; if it climbs toward the cap,
#   bump machine_type to e2-custom-2-6144 and re-apply.
gcloud compute forwarding-rules list --global --format='table(name,IPAddress,portRange)'
#   apiv2 rules gone; remaining: webpage :80 + :443 (+ any staging).
```

**Watch for a few days:** E2 is oversubscribed vs T2D's dedicated cores; at 35%
avg there's headroom, but confirm p99 latency and CPU haven't regressed, and that
the reduced-DB working set keeps RAM under 4 GB.

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
- **Phase 4** (frontend torn down): recovery is `git revert` of the `terraform/`
  frontend gating + `terraform apply` to recreate the API IP/proxies/rules, then
  point apiv2 DNS back. The **new IP will differ** from 34.102.163.196 — cutover
  again via DNS. Prefer fixing forward on the shared LB.
- **VM**: set `machine_type` back to `t2d-standard-2` and apply (another MIG roll).
- **Phase 5 / preload**: effectively irreversible on browser timescales — serve
  `max-age=0` and request removal at hstspreload.org, expect months. This is why
  :80 stays until preload is certain.
```
