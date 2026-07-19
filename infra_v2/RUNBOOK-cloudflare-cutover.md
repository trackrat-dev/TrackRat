# Runbook: Eliminate the global forwarding-rule minimum charge (Cloudflare cutover)

## Why

The `Cloud Load Balancer Forwarding Rule Minimum Global` SKU bills a **flat
$0.025/hr (~$0.60/day, ~$219/yr) for the first 5 global forwarding rules,
aggregated per project** — not per rule and not per load balancer. All of
TrackRat's forwarding rules are global and in one project (`trackrat-v2`), so
they share a single minimum bucket. Reducing the rule *count* (the
`RUNBOOK-lb-consolidation.md` work: 6 → 4 → 1) does **not** lower this SKU at
all — it stays $0.60/day until the project has **zero** global forwarding rules.

Switching to a regional or passthrough load balancer does not help either:
regional forwarding rules have their own identical minimum, and forwarding-rule
billing is the same across all LB types. The only way to $0 is to stop using a
Google-managed load balancer entirely.

## Target architecture

Front everything with Cloudflare (DNS is already there) and delete both Google
load balancers:

- **APIs** (`apiv2`, `staging.apiv2`) → **Cloudflare Tunnel** (`cloudflared`
  container in `backend_v2/docker-compose.yml`). Cloudflare terminates TLS at
  its edge and routes the hostname to `http://api:8000` over the private Docker
  network. The VM needs no public ingress, no origin certificate, and no reverse
  proxy — the origin stays exactly as it is today (plain HTTP on `:8000`).
- **Static site** (`trackrat.net`, `www`) → keep the GCS bucket, front it with
  Cloudflare (orange-cloud) via host/path transform rules. (Decision: keep the
  existing GCS deploy pipeline rather than migrating to Pages.)

End state: no `google_compute_*_forwarding_rule` anywhere → SKU $0. Also sheds
the webpage backend-bucket/CDN, two managed SSL certs, url maps, and the API's
static IPs.

## Repo levers already in place

- `backend_v2/docker-compose.yml` — `cloudflared` service under
  `profiles: ["tunnel"]`. Inert unless the startup script activates the profile.
- `infra_v2/terraform/compute.tf` — startup script reads
  `trackrat-cloudflare-tunnel-token-$ENVIRONMENT` from Secret Manager. If present,
  it appends `CLOUDFLARE_TUNNEL_TOKEN` + `COMPOSE_PROFILES=tunnel` to `.env`, so
  `cloudflared` starts. If absent (e.g. production today), the tunnel stays off.
- `infra_v2/terraform/secrets.tf` — staging-gated IAM grant so the staging VM SA
  can read the tunnel-token secret.
- `infra_v2/terraform/variables.tf` — `frontend_via_cloudflare` (default `false`).
  Flipping the committed default to `true` tears down the dedicated API frontend
  (IP, url map, proxies, forwarding rules). **This is the teardown trigger.**

Everything ships in the safe/off position: merging the branch changes nothing
about the live load balancers until the manual steps below are done.

---

## Phase 1 — Staging pilot (zero production risk)

The staging API LB is independent of production, and the tunnel runs *alongside*
the existing LB, so nothing is torn down until after the tunnel is verified.

### 1a. Create the tunnel (Cloudflare dashboard)

1. Zero Trust → Networks → Tunnels → **Create a tunnel** → *Cloudflared* type.
   Name it `trackrat-staging`. Copy the **tunnel token** (the long value in the
   `--token ...` install command).
2. Add a **public hostname**: `staging.apiv2.trackrat.net` → service
   `HTTP` → `api:8000`. (Adding it here creates the proxied DNS record
   automatically at cutover — see 1d.) For a fully risk-free dry run, use a
   throwaway hostname like `staging-tunnel.trackrat.net` first and only add the
   real hostname at 1d.

### 1b. Store the token in Secret Manager and grant the VM read access

```bash
# Create the secret with the tunnel token
printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets create trackrat-cloudflare-tunnel-token-staging \
  --project=trackrat-v2 --replication-policy=automatic --data-file=-
# If it already exists, add a new version instead:
# printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets versions add trackrat-cloudflare-tunnel-token-staging --project=trackrat-v2 --data-file=-

# Grant the staging VM service account read access
gcloud secrets add-iam-policy-binding trackrat-cloudflare-tunnel-token-staging \
  --project=trackrat-v2 \
  --member="serviceAccount:trackrat-staging@trackrat-v2.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

The grant is done here (not in Terraform) so merging the branch stays inert: the
startup script reads the secret tolerantly, so a missing secret just leaves the
tunnel off. Fold the grant into `secrets.tf` once the tunnel is permanent and
both environments have a token (see the note in that file).

### 1c. Ship the connector (repo → staging)

Merge this branch to `main`. The staging Cloud Build runs Terraform (new
instance template) and rolls a new MIG instance. On boot the startup script
finds the staging secret, activates the `tunnel` profile, and starts
`cloudflared`. Verify:

- Dashboard: the tunnel shows **HEALTHY** with one connector.
- Logs: `PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env staging --search cloudflared`
- If you used a dry-run hostname: `curl -sS https://staging-tunnel.trackrat.net/health/ready` returns 200.

The staging LB is still live and serving `staging.apiv2.trackrat.net` at this
point — no impact yet.

### 1d. Cut over DNS (Cloudflare)

Point `staging.apiv2.trackrat.net` at the tunnel. If you added the real hostname
in 1a, this record already exists (proxied/orange) — just delete the old
grey `A` record that points at the staging LB IP. Then verify:

```bash
curl -sS https://staging.apiv2.trackrat.net/health/ready   # 200 via Cloudflare
curl -sSI https://staging.apiv2.trackrat.net/api/v2/trains/recent-departures?from=NY | head -n1
```

Confirm responses carry Cloudflare headers (`server: cloudflare`, `cf-ray`).
Give it a few minutes and re-run `scripts/validate-staging.sh https://staging.apiv2.trackrat.net`.

### 1e. Tear down the staging API LB

Only now, with the tunnel serving the real hostname: set
`frontend_via_cloudflare` default to `true` in
`infra_v2/terraform/variables.tf`, commit, and let the staging apply run. The
plan should destroy exactly the staging frontend — `google_compute_global_address.trackrat[0]`,
`google_compute_url_map.trackrat[0]` (+ redirect), both target proxies, and both
`google_compute_global_forwarding_rule.trackrat_*[0]` — and nothing else. The
backend service, MIG, health check, and cert stay.

**Rollback (any point in Phase 1):** flip the `staging.apiv2` DNS record back to
a grey `A` record pointing at the staging LB IP. The LB still exists until 1e; if
you've already done 1e, `git revert` the `frontend_via_cloudflare` flip and
re-apply to recreate it (a new IP — update DNS to match).

---

## Phase 2 — Production API (`apiv2.trackrat.net`)

Production `apiv2` is served by the **webpage** LB (shared IP `136.110.151.144`),
so this phase moves only DNS + origin; the webpage LB keeps serving the static
site until Phase 4.

1. Create a second tunnel `trackrat-production`, public hostname
   `apiv2.trackrat.net` → `HTTP` → `api:8000`. Store its token as
   `trackrat-cloudflare-tunnel-token-production`.
2. In `secrets.tf`, generalize the IAM grant to production too (drop the
   `count = var.environment == "staging"` gate, or add a production copy). The
   startup script already reads the `-$ENVIRONMENT` secret, so no compute.tf
   change is needed.
3. Deploy to production, confirm the connector is HEALTHY.
4. Flip `apiv2.trackrat.net` DNS to the production tunnel and verify.
5. Set `frontend_via_cloudflare = true` for production as well — but note
   production's dedicated frontend is already gone (consolidated), so the real
   removal of `apiv2` from Google happens in Phase 4 when the webpage LB's
   host-route for `apiv2` is deleted.

**Rollback:** repoint `apiv2` DNS at `136.110.151.144` (grey). The webpage LB
still host-routes it.

---

## Phase 3 — Static site behind Cloudflare

Keep the GCS bucket + existing deploy pipeline (`scripts/deploy-webpage.sh`,
`gs://trackrat-webpage-production`). Front it with Cloudflare:

1. Orange-cloud (proxy) `trackrat.net` and `www.trackrat.net`.
2. Set the origin to the bucket's HTTPS endpoint and add a Cloudflare
   **Transform Rule** rewriting the `Host` header to `storage.googleapis.com`
   and the path to `/trackrat-webpage-production<path>`; add a rule mapping `/`
   and extensionless paths to `…/index.html` so client-side routing and the SPA
   entrypoint resolve. Preserve the existing cache headers (the bucket already
   sets `Cache-Control` per object; keep Cloudflare's cache respecting origin).
3. Verify `https://trackrat.net`, `https://www.trackrat.net`, deep links, and
   `/.well-known/apple-app-site-association` (must stay `application/json`).

**Rollback:** grey-cloud the records back to `136.110.151.144`.

---

## Phase 4 — Delete the webpage LB → SKU $0

Once `apiv2`, `trackrat.net`, and `www` are all served by Cloudflare and
verified, remove the webpage LB in `infra_v2/terraform-webpage/`: the two
`google_compute_global_forwarding_rule.webpage_production_*`, the target
proxies, url map, backend-bucket + CDN, managed cert, and the
`google_compute_global_address.webpage_production_ip`. Also remove the now-unused
`trackrat-production-cert` / API frontend remnants in `infra_v2/terraform/`.

After this apply, `gcloud compute forwarding-rules list` should return **nothing
global**, and the `Cloud Load Balancer Forwarding Rule Minimum Global` SKU drops
to $0 on the next billing cycle.

**Point of no easy return:** Phase 4 deletes the shared IP. Roll back only by
re-applying the webpage LB Terraform (new IP) and repointing DNS. Do Phase 4 only
after Phases 2–3 have been stable for a day.

---

## Verification cheatsheet

```bash
# Global forwarding rules currently billed (goal: empty after Phase 4)
gcloud compute forwarding-rules list --global --project=trackrat-v2

# Tunnel connector health lives in the Cloudflare Zero Trust dashboard;
# app-side, confirm cloudflared came up:
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env staging --search cloudflared

# End-to-end via Cloudflare (expect cf-ray header)
curl -sSI https://staging.apiv2.trackrat.net/health/ready
bash scripts/validate-staging.sh https://staging.apiv2.trackrat.net
```
