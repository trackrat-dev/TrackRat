# TrackRat Webpage Infrastructure
#
# Standalone Terraform root for webpage infrastructure. Separate from the
# API backend Terraform (infra_v2/terraform/) because these are shared/global
# resources that don't vary per environment workspace.
#
# Manages:
#   - Cloud Build triggers for both staging and production webpage deployments
#
# Usage:
#   cd infra_v2/terraform-webpage
#   terraform init
#   terraform plan -var="project_id=trackrat-v2"
#   terraform apply -var="project_id=trackrat-v2"
#
# NOTE: These resources were originally managed by universal-links-deployment/
# with local Terraform state. To import existing resources:
#   terraform import google_cloudbuild_trigger.webpage_staging \
#     projects/trackrat-v2/locations/us-east4/triggers/trackrat-webpage-staging
#   terraform import google_cloudbuild_trigger.webpage_production \
#     projects/trackrat-v2/locations/us-east4/triggers/trackrat-webpage-production

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "trackrat-v2-terraform-state"
    prefix = "terraform/webpage"
  }
}

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "trackrat-v2"
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ============================================
# Webpage hosting
# ============================================
# Not managed here. staging.trackrat.net, trackrat.net and www.trackrat.net are
# served by Cloudflare Workers Static Assets (issue #1713); the Workers and
# their custom domains are defined in webpage_v2/wrangler.jsonc and deployed by
# the cloudbuild files the triggers below run.
#
# None of the GCP serving path is kept. Both load balancers were
# deleted directly in GCP (staging as cost cleanup, production on 2026-08-08),
# the production static IP 136.110.151.144 is released by applying this root
# (issue #1762, RUNBOOK-cloudflare-cutover.md P6), and so are the
# trackrat-webpage-staging / trackrat-webpage-production buckets, which nothing
# reads or writes (issue #1763, P5 step 6). Do not re-add any of it: every
# global forwarding rule re-bills the "Cloud Load Balancer Forwarding Rule
# Minimum Global" SKU the cutover removed, and a rebuilt LB comes back on a new
# IP. HSTS now comes from webpage_v2/public/_headers, not a backend bucket's
# custom_response_headers.

# ============================================
# Cloud Build triggers for webpage deployment
# ============================================
# Uses 2nd gen Cloud Build connection (trackrat-github) in us-east4.
# Triggers deploy webpage on branch push when webpage_v2/ files change, OR when
# the build config itself changes. Each cloudbuild file is in its own trigger's
# included_files because it bakes _API_BASE_URL into the bundle as
# VITE_API_BASE_URL at build time: without it, editing that substitution deploys
# nothing and the live site keeps calling the previous API host until some
# unrelated webpage_v2/ change happens to land. That is exactly what the staging
# API rename hit (PR #1712) — the new host reached the repo but not the bundle.

resource "google_cloudbuild_trigger" "webpage_staging" {
  name            = "trackrat-webpage-staging"
  description     = "Deploy webpage to staging on push to main (webpage_v2/ changes)"
  location        = "us-east4"
  service_account = "projects/${var.project_id}/serviceAccounts/trackrat-staging@${var.project_id}.iam.gserviceaccount.com"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/us-east4/connections/trackrat-github/repositories/trackrat-dev-TrackRat"
    push {
      branch = "^main$"
    }
  }

  included_files = ["webpage_v2/**", "infra_v2/cloudbuild-webpage-staging.yaml"]
  filename       = "infra_v2/cloudbuild-webpage-staging.yaml"
}

resource "google_cloudbuild_trigger" "webpage_production" {
  name            = "trackrat-webpage-production"
  description     = "Deploy webpage to production on push to production (webpage_v2/ changes)"
  location        = "us-east4"
  service_account = "projects/${var.project_id}/serviceAccounts/trackrat-staging@${var.project_id}.iam.gserviceaccount.com"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/us-east4/connections/trackrat-github/repositories/trackrat-dev-TrackRat"
    push {
      branch = "^production$"
    }
  }

  included_files = ["webpage_v2/**", "infra_v2/cloudbuild-webpage.yaml"]
  filename       = "infra_v2/cloudbuild-webpage.yaml"
}
