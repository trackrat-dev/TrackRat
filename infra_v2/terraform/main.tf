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

  # Production's HTTPS frontend (IP, url map, proxies, forwarding rules) is
  # served by the consolidated webpage load balancer in
  # infra_v2/terraform-webpage (apiv2.trackrat.net is host-routed there to
  # this workspace's backend service). This drops production's 2 dedicated
  # global forwarding rules. Staging keeps its own dedicated API LB.
  create_api_frontend = var.environment != "production"
}
