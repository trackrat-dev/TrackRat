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
  container in the isolated `backend_v2/docker-compose.tunnel.yml`). Cloudflare terminates TLS at
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

- `infra_v2/terraform/variables.tf` — **`enable_cloudflare_tunnel`** (default
  `false`). Master on/off switch for the connector. `cloudflared` starts **only**
  when this flag is `true` **and** the token secret is present — secret-existence
  alone is no longer enough (issue #1578). **This is the connector trigger.**
- `backend_v2/docker-compose.tunnel.yml` — the `cloudflared` service, isolated
  from `docker-compose.yml`. It is never parsed during the api/db bring-up, so a
  malformed connector config or invalid token cannot abort the API.
- `infra_v2/terraform/compute.tf` — startup script reads
  `trackrat-cloudflare-tunnel-token-$ENVIRONMENT` from Secret Manager. When
  `enable_cloudflare_tunnel=true` and the token is non-empty, it writes
  `CLOUDFLARE_TUNNEL_TOKEN` to `.env`, brings `db`/`api` up from
  `docker-compose.yml` alone, then starts `cloudflared` in a **separate,
  non-fatal** `compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d
  --no-deps cloudflared` (`--no-deps` keeps `api` out of the invocation's scope
  entirely, issue #1594). If the flag is off or the token absent, the tunnel
  stays fully off and any stale `docker-compose.tunnel.yml` on the data disk is
  removed, so file presence always means "enabled this boot". The shutdown
  script drains the connector when that file is present — a short, non-fatal
  `stop cloudflared` before the api/db stop, so Cloudflare's edge deregisters
  this instance before the API goes away (issue #1594).
- `infra_v2/terraform/secrets.tf` — a NOTE only; the tunnel-token secret and its
  IAM grant are intentionally **not** Terraform-managed during the pilot (an IAM
  binding on a not-yet-created secret would fail the apply). The staging VM SA is
  granted read access out-of-band via `gcloud` in step 1b.
- `infra_v2/terraform/variables.tf` — `frontend_via_cloudflare` (default `false`).
  Flipping the committed default to `true` tears down the dedicated API frontend
  (IP, url map, proxies, forwarding rules). **This is the LB teardown trigger**,
  independent of `enable_cloudflare_tunnel`.

Everything ships in the safe/off position: with `enable_cloudflare_tunnel=false`,
merging the branch neither starts the connector nor touches the live load
balancers until the steps below flip the flags.

## Current state & ordering constraints (post-#1592, as of 2026-07-21)

Read this before the next enable attempt (issue #1594).

- **The 2026-07-19 crash-looping staging connector is gone.** It could not
  survive the first post-merge staging deploy: `cloudbuild-staging.yaml` scales
  the MIG to 0 and back to 1, which *deletes* the instance — the replacement
  boots with a fresh boot disk, so no Docker container state (including a
  `restart: unless-stopped` connector) carries over. It stopped on 2026-07-20
  22:11Z with the old instance's shutdown. Terraform changes apply
  automatically too (`cloudbuild-terraform.yaml` triggers on
  `infra_v2/terraform/**`, and the deploy pipelines wait for an in-flight
  Terraform build), so the #1592 startup script — including its
  `down --remove-orphans` cleanup — is the active staging template. Nothing
  needs to be revoked or recreated to keep the connector off.
- **The staging token secret still holds the invalid token** from the failed
  pilot. With the flag off it is inert, but **replacing it with a fresh valid
  token (step 1b's "add a new version" path) is a mandatory precondition of
  step 1c** — re-enabling against the stale token just crash-loops the
  connector again (contained now: api/db unaffected, but the pilot fails).
- **Production deploys are different: the orphan window is real there.**
  `cloudbuild.yaml` uses `rolling-action restart`, which reboots the *same*
  instance — the boot disk and Docker container state survive, so a
  previously-started connector would come back after a reboot and only a
  startup script with `down --remove-orphans` (i.e. the #1592 template,
  installed via a production Terraform apply) clears it. Today this is moot —
  the `production` branch carries no tunnel code at all and no production
  token secret exists — but it is why the promotion ordering in Phase 2
  matters.
- **`enable_cloudflare_tunnel` is one committed default shared by both
  Terraform workspaces** (`cloudbuild-terraform.yaml` passes only
  `environment` and `project_id`). Once step 1c flips it to `true`, any
  routine main → production promotion arms production as well, leaving the
  absent production secret as the *only* remaining gate. That is how the
  flag-AND-token gate is designed, but be deliberate about it: create the
  production secret only when you actually intend Phase 2.

---

## Phase 1 — Staging pilot (production untouched, but not risk-free on staging)

The staging API LB is independent of production, and the tunnel runs *alongside*
the existing LB, so nothing is torn down until after the tunnel is verified.

Two caveats keep this from being literally "zero risk" — both on **staging only**:

- The connector is now isolated in `docker-compose.tunnel.yml` and brought up
  non-fatally *after* `db`/`api` (issue #1578), so a bad token/config can no
  longer abort the API the way the 2026-07-19 outage did. It still shares the VM,
  so treat a first enable as a real change, not a no-op.
- Since #1577, `staging.trackrat.net` (the **webpage**) is host-routed by the
  staging **API** LB. Tearing that LB down at 1e therefore also drops staging
  webpage serving — account for it before flipping `frontend_via_cloudflare`.

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

> The secret already exists and currently holds the **invalid token from the
> failed 2026-07 pilot** — the `versions add` path below is the one you want.
> Do not skip it: enabling the flag against the stale token crash-loops the
> connector (contained, but the pilot fails again).

```bash
# The secret already exists (stale token) — add a new version:
printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets versions add trackrat-cloudflare-tunnel-token-staging \
  --project=trackrat-v2 --data-file=-
# Only if it were ever deleted, recreate it instead:
# printf '%s' '<TUNNEL_TOKEN>' | gcloud secrets create trackrat-cloudflare-tunnel-token-staging \
#   --project=trackrat-v2 --replication-policy=automatic --data-file=-

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

Set `enable_cloudflare_tunnel = true` in `infra_v2/terraform/variables.tf`
(committed default, not `-var`) and merge to `main`. The staging Cloud Build
runs Terraform (new instance template) and rolls a new MIG instance. On boot the
startup script finds the staging secret, and — because the flag is now on —
fetches `docker-compose.tunnel.yml` and starts `cloudflared` in its isolated,
non-fatal `up`. (With the flag left `false`, the secret alone does nothing.)
Verify:

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

0. **Promote first.** The `production` branch must already carry the #1592
   isolation (plus the #1594 hardening) and its Terraform must have applied —
   the production instance template only updates from the `production` branch
   — **before** the production token secret is created. Production's
   `rolling-action restart` deploys preserve Docker state across reboots (see
   "Current state & ordering constraints" above), so only the isolated,
   flag-gated startup script makes a bad production token a contained failure
   instead of a repeat of the 2026-07-19 outage at production scale.
1. Create a second tunnel `trackrat-production`, public hostname
   `apiv2.trackrat.net` → `HTTP` → `api:8000`. Store its token as
   `trackrat-cloudflare-tunnel-token-production`.
2. Grant the **production** VM service account read access to the production
   secret, exactly as step 1b did for staging (there is no Terraform grant to
   generalize — the pilot keeps this out-of-band):

   ```bash
   gcloud secrets add-iam-policy-binding trackrat-cloudflare-tunnel-token-production \
     --project=trackrat-v2 \
     --member="serviceAccount:trackrat-production@trackrat-v2.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

   The startup script already reads the `-$ENVIRONMENT` secret, so no compute.tf
   change is needed. (Fold both grants into `secrets.tf` once the tunnel is
   permanent and both secrets exist — see the note in that file.)
3. Deploy to production, confirm the connector is HEALTHY.
4. Flip `apiv2.trackrat.net` DNS to the production tunnel and verify.
5. Set `frontend_via_cloudflare = true` for production as well — but note
   production's dedicated frontend is already gone (consolidated), so the real
   removal of `apiv2` from Google happens in Phase 4 when the webpage LB's
   host-route for `apiv2` is deleted.

**Rollback:** repoint `apiv2` DNS at `136.110.151.144` (grey). The webpage LB
still host-routes it.

> **⚠️ Observability follow-up (required before relying on the daily usage report).**
> `scripts/server-usage.py::fetch_lb_logs` queries only
> `resource.type="http_load_balancer"`. Once API traffic rides the tunnel it no
> longer traverses the GCP HTTP LB, so the usage report and the daily-report
> routine will silently show **zero API traffic** even while users are active.
> Before this phase, add a post-cutover traffic source — a Cloudflare log source
> (Logpush / GraphQL Analytics) or the backend's own request stats / `cos_containers`
> app logs — so the report keeps working. (Client-IP attribution itself is already
> handled: `api/utils.get_client_ip` reads Cloudflare's `CF-Connecting-IP`.)

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
