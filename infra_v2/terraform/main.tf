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
  # Where clients reach the API, advertised by the api_url output and probed by
  # the production uptime check (monitoring.tf). Staging's API is served at
  # staging-api.trackrat.net via the Cloudflare Tunnel: Universal SSL covers only
  # the apex and ONE subdomain level (the edge cert's SANs are trackrat.net and
  # *.trackrat.net), so the two-label staging.apiv2.trackrat.net cannot be proxied
  # without paid Advanced Certificate Manager — hence the rename. See
  # infra_v2/RUNBOOK-cloudflare-cutover.md.
  public_api_domain = var.environment == "production" ? "apiv2.trackrat.net" : "staging-api.trackrat.net"
  use_spot_vm       = var.environment == "staging"

  # TRACKRAT_DISABLED_DATA_SOURCES for THIS workspace only. Resolved from the
  # per-environment map so a staging soak (e.g. SEPTA, issue #1634) cannot arm
  # the next production apply to enable the same source. Sorted for a stable
  # .env line — a set reordering would otherwise rewrite the startup script and
  # churn the instance template on an unrelated apply.
  disabled_data_sources = join(",", sort(var.disabled_data_sources[var.environment]))
}
