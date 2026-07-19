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

# Derive domain from environment
# Production uses on-demand VMs for stability; staging uses spot for cost savings
locals {
  domain      = var.environment == "production" ? "apiv2.trackrat.net" : "staging.apiv2.trackrat.net"
  use_spot_vm = var.environment == "staging"

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
}
