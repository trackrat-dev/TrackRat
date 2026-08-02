# TrackRat V2 Infrastructure
# Simplified deployment using MIG + PostgreSQL container + persistent disk

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
  }

  backend "gcs" {
    bucket = "trackrat-v2-terraform-state"
    prefix = "terraform/state"
    # Note: Uses Terraform workspaces for environment separation
    # State stored at: terraform/state/<workspace>/default.tfstate
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Derive domain from environment.
#
# Staging and production are kept deliberately identical in resources — same
# machine type (var.machine_type), same disk (var.disk_size_gb), same MIG size —
# so staging is a faithful rehearsal of production and a sizing change made once
# reaches both. The ONLY intended divergence is the provisioning model:
# staging runs SPOT for cost savings, production runs on-demand for stability.
# Do not reintroduce a per-environment machine_type/disk override; change the
# shared variable instead so both environments move together.
locals {
  # NOTE: staging's API is served at staging-api.trackrat.net via the Cloudflare
  # Tunnel, NOT at the name below. Cloudflare Universal SSL covers only the apex
  # and ONE subdomain level (the edge cert's SANs are trackrat.net and
  # *.trackrat.net), so the two-label staging.apiv2.trackrat.net cannot be
  # proxied without paid Advanced Certificate Manager — hence the rename.
  # This local is deliberately left on the old name because its only remaining
  # consumers are the LB's managed cert (loadbalancer.tf) and an output; DNS for
  # staging-api points at Cloudflare, so minting a Google cert for it would just
  # sit in FAILED_NOT_VISIBLE. Both are destroyed when frontend_via_cloudflare
  # flips — see infra_v2/RUNBOOK-cloudflare-cutover.md.
  domain      = var.environment == "production" ? "apiv2.trackrat.net" : "staging.apiv2.trackrat.net"
  use_spot_vm = var.environment == "staging"

  # TRACKRAT_DISABLED_DATA_SOURCES for THIS workspace only. Resolved from the
  # per-environment map so a staging soak (e.g. SEPTA, issue #1634) cannot arm
  # the next production apply to enable the same source. Sorted for a stable
  # .env line — a set reordering would otherwise rewrite the startup script and
  # churn the instance template on an unrelated apply.
  disabled_data_sources = join(",", sort(var.disabled_data_sources[var.environment]))

  # Once var.consolidate_api_lb is flipped, production's HTTPS frontend (IP,
  # url map, proxies, forwarding rules) is served by the consolidated webpage
  # load balancer in infra_v2/terraform-webpage (apiv2.trackrat.net is
  # host-routed there to this workspace's backend service), dropping
  # production's 2 dedicated global forwarding rules. Gated on the variable
  # (default false) because infra_v2/cloudbuild-terraform.yaml auto-applies
  # this root on every deploy-branch push — the teardown must be an explicit
  # runbook Phase-4 action, never a side effect of an unrelated deploy.
  #
  # var.frontend_via_cloudflare drops this workspace's dedicated API frontend
  # once the environment's API is fronted by a Cloudflare Tunnel instead (see
  # infra_v2/RUNBOOK-cloudflare-cutover.md). Same committed-default discipline
  # as consolidate_api_lb: flip it to true ONLY after the tunnel is up and DNS
  # is cut over, or the push-triggered apply takes the API offline.
  create_api_frontend = !var.frontend_via_cloudflare && !(var.environment == "production" && var.consolidate_api_lb)

  # Staging serves its webpage from this same LB, mirroring how production's
  # single consolidated LB serves both apiv2 and the webpage bucket. The staging
  # webpage's dedicated frontend was decommissioned for cost, so instead of
  # re-adding one we host-route staging.trackrat.net through the surviving
  # staging API frontend (no extra IP or forwarding rules). Gated on staging AND
  # on the API frontend existing, so a Cloudflare-tunnel cutover
  # (frontend_via_cloudflare=true) cleanly drops the webpage routing with it.
  serve_webpage_on_api_lb = var.environment == "staging" && local.create_api_frontend
  webpage_staging_domain  = "staging.trackrat.net"
  webpage_staging_bucket  = "trackrat-webpage-staging"
}
