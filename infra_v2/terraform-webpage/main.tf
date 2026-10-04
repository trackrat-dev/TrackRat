# TrackRat Webpage Infrastructure
#
# Standalone Terraform root for webpage infrastructure. Separate from the
# API backend Terraform (infra_v2/terraform/) because these are shared/global
# resources that don't vary per environment workspace.
#
# Manages:
#   - Staging webpage: GCS bucket only (the staging LB frontend — IP, cert,
#     proxies, url maps, forwarding rules — was decommissioned out-of-band as
#     cost cleanup; the bucket remains as the staging deploy target)
#   - Production webpage: GCS bucket only (the LB frontend was retired — see
#     the production section below)
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
#   terraform import google_storage_bucket.webpage_staging trackrat-webpage-staging
#   terraform import google_storage_bucket_iam_member.staging_public_access \
#     "trackrat-webpage-staging roles/storage.objectViewer allUsers"
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
# Staging webpage infrastructure
# ============================================
# Bucket only. The staging LB frontend (trackrat-webpage-staging-ip
# 35.190.73.247, cert, proxies, url maps, forwarding rules) was deleted
# directly in GCP as cost cleanup and is intentionally not managed here —
# re-adding it would recreate the stack on a new IP with a cert that cannot
# provision (staging.trackrat.net DNS no longer points at it).
#
# The bucket is NO LONGER A DEPLOY TARGET: staging.trackrat.net serves from
# Cloudflare Workers Static Assets and cloudbuild-webpage-staging.yaml uploads
# there instead (issue #1713). It is kept for exactly one reason — it holds the
# last GCS build, so it is the rollback artifact if the cutover has to be
# undone. DELETE IT (this resource, the IAM member below, and the output) once
# staging has soaked; leaving it costs storage and makes it look like a live
# destination. force_destroy = true, so the apply empties it.

# GCS bucket for staging webpage
resource "google_storage_bucket" "webpage_staging" {
  name          = "trackrat-webpage-staging"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html" # SPA fallback
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Make staging bucket publicly readable
resource "google_storage_bucket_iam_member" "staging_public_access" {
  bucket = google_storage_bucket.webpage_staging.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Staging outputs
output "staging_webpage_bucket" {
  value       = google_storage_bucket.webpage_staging.name
  description = "Staging GCS bucket name"
}

# ============================================
# Production webpage infrastructure
# ============================================
# Bucket only. trackrat.net / www.trackrat.net are served by Cloudflare Workers
# Static Assets (issue #1713), so the production LB (backend bucket, url map,
# managed cert, proxies, forwarding rules) was deleted directly in GCP on
# 2026-08-08; its static IP 136.110.151.144 was retained then and is released
# by applying this root (issue #1762, RUNBOOK-cloudflare-cutover.md P6). Do not
# re-add any of it: every global forwarding rule re-bills the "Cloud Load
# Balancer Forwarding Rule Minimum Global" SKU the cutover removed, and a
# rebuilt LB comes back on a new IP. HSTS now comes from
# webpage_v2/public/_headers, not the backend bucket's custom_response_headers.
#
# cloudbuild-webpage.yaml still syncs each build here, but nothing serves the
# bucket; runbook P5 step 5 retires that sync.

# GCS bucket for production webpage
resource "google_storage_bucket" "webpage_production" {
  name          = "trackrat-webpage-production"
  location      = "US"
  force_destroy = false # prod safety: require manual emptying before destroy

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html" # SPA fallback
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Make production bucket publicly readable
resource "google_storage_bucket_iam_member" "production_public_access" {
  bucket = google_storage_bucket.webpage_production.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

output "production_webpage_bucket" {
  value       = google_storage_bucket.webpage_production.name
  description = "Production GCS bucket name"
}

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
