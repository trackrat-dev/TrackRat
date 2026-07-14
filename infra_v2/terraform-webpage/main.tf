# TrackRat Webpage Infrastructure
#
# Standalone Terraform root for webpage infrastructure. Separate from the
# API backend Terraform (infra_v2/terraform/) because these are shared/global
# resources that don't vary per environment workspace.
#
# Manages:
#   - Staging webpage: GCS bucket + CDN + LB for staging.trackrat.net
#   - Production webpage: GCS bucket + CDN + LB for trackrat.net / www.trackrat.net
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
#   terraform import google_compute_backend_bucket.webpage_staging_backend \
#     projects/trackrat-v2/global/backendBuckets/trackrat-webpage-staging-backend
#   terraform import google_compute_url_map.webpage_staging \
#     projects/trackrat-v2/global/urlMaps/trackrat-webpage-staging-map
#   terraform import google_compute_managed_ssl_certificate.webpage_staging_cert \
#     projects/trackrat-v2/global/sslCertificates/trackrat-webpage-staging-cert
#   terraform import google_compute_global_address.webpage_staging_ip \
#     projects/trackrat-v2/global/addresses/trackrat-webpage-staging-ip
#   terraform import google_compute_target_https_proxy.webpage_staging_proxy \
#     projects/trackrat-v2/global/targetHttpsProxies/trackrat-webpage-staging-https-proxy
#   terraform import google_compute_global_forwarding_rule.webpage_staging_https \
#     projects/trackrat-v2/global/forwardingRules/trackrat-webpage-staging-https
#   terraform import google_compute_url_map.webpage_staging_https_redirect \
#     projects/trackrat-v2/global/urlMaps/trackrat-webpage-staging-https-redirect
#   terraform import google_compute_target_http_proxy.webpage_staging_http_proxy \
#     projects/trackrat-v2/global/targetHttpProxies/trackrat-webpage-staging-http-proxy
#   terraform import google_compute_global_forwarding_rule.webpage_staging_http \
#     projects/trackrat-v2/global/forwardingRules/trackrat-webpage-staging-http
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

# CDN backend bucket for staging
resource "google_compute_backend_bucket" "webpage_staging_backend" {
  name        = "trackrat-webpage-staging-backend"
  description = "Backend bucket for TrackRat staging webpage"
  bucket_name = google_storage_bucket.webpage_staging.name
  enable_cdn  = true

  cdn_policy {
    cache_mode       = "CACHE_ALL_STATIC"
    default_ttl      = 300  # 5 min (shorter for staging)
    max_ttl          = 3600 # 1 hour
    client_ttl       = 300
    negative_caching = true
  }
}

# URL map for staging
resource "google_compute_url_map" "webpage_staging" {
  name            = "trackrat-webpage-staging-map"
  description     = "URL map for TrackRat staging webpage"
  default_service = google_compute_backend_bucket.webpage_staging_backend.id
}

# SSL certificate for staging.trackrat.net
resource "google_compute_managed_ssl_certificate" "webpage_staging_cert" {
  name = "trackrat-webpage-staging-cert"

  managed {
    domains = ["staging.trackrat.net"]
  }
}

# Global static IP for staging
resource "google_compute_global_address" "webpage_staging_ip" {
  name = "trackrat-webpage-staging-ip"
}

# HTTPS proxy for staging
resource "google_compute_target_https_proxy" "webpage_staging_proxy" {
  name             = "trackrat-webpage-staging-https-proxy"
  url_map          = google_compute_url_map.webpage_staging.id
  ssl_certificates = [google_compute_managed_ssl_certificate.webpage_staging_cert.id]
}

# HTTPS forwarding rule for staging
resource "google_compute_global_forwarding_rule" "webpage_staging_https" {
  name       = "trackrat-webpage-staging-https"
  target     = google_compute_target_https_proxy.webpage_staging_proxy.id
  port_range = "443"
  ip_address = google_compute_global_address.webpage_staging_ip.address
}

# HTTP to HTTPS redirect for staging
resource "google_compute_url_map" "webpage_staging_https_redirect" {
  name = "trackrat-webpage-staging-https-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "PERMANENT_REDIRECT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "webpage_staging_http_proxy" {
  name    = "trackrat-webpage-staging-http-proxy"
  url_map = google_compute_url_map.webpage_staging_https_redirect.id
}

resource "google_compute_global_forwarding_rule" "webpage_staging_http" {
  name       = "trackrat-webpage-staging-http"
  target     = google_compute_target_http_proxy.webpage_staging_http_proxy.id
  port_range = "80"
  ip_address = google_compute_global_address.webpage_staging_ip.address
}

# Staging outputs
output "staging_webpage_ip" {
  value       = google_compute_global_address.webpage_staging_ip.address
  description = "Point staging.trackrat.net DNS A record to this IP"
}

output "staging_webpage_bucket" {
  value       = google_storage_bucket.webpage_staging.name
  description = "Staging GCS bucket name"
}

# ============================================
# Production webpage infrastructure
# ============================================
# Mirrors staging, sized/tuned for production. Resources are created in
# trackrat-v2 to consolidate ownership with the rest of the stack.
# Cutover from the legacy trackrat-prod LB is a DNS-only operation: point
# trackrat.net / www.trackrat.net A records at production_webpage_ip output.

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

# CDN backend bucket for production
resource "google_compute_backend_bucket" "webpage_production_backend" {
  name        = "trackrat-webpage-production-backend"
  description = "Backend bucket for TrackRat production webpage"
  bucket_name = google_storage_bucket.webpage_production.name
  enable_cdn  = true

  # HSTS on the apex (trackrat.net) + www responses. Required to submit
  # trackrat.net to the browser HSTS preload list (includeSubDomains covers
  # apiv2/www). The apiv2 backend sets the same header via FastAPI middleware.
  # NOTE: `preload` here is a standing commitment — do not remove it while the
  # domain is on the preload list. See infra_v2/RUNBOOK-lb-consolidation.md.
  custom_response_headers = [
    "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
  ]

  cdn_policy {
    cache_mode       = "CACHE_ALL_STATIC"
    default_ttl      = 3600  # 1 hour fallback (objects' own Cache-Control wins)
    max_ttl          = 86400 # 24 hours
    client_ttl       = 3600
    negative_caching = true
  }
}

# API backend service (owned by infra_v2/terraform/ production workspace).
# Looked up by its stable name so the consolidated LB can host-route apiv2 to
# it without cross-root state coupling. Must already exist (it does, as long
# as the production API workspace is applied).
data "google_compute_backend_service" "api_production" {
  name = "trackrat-production-backend"
}

# URL map for production — consolidated load balancer:
#   apiv2.trackrat.net        -> API backend service (VM MIG)
#   trackrat.net / www.*      -> webpage GCS bucket (default)
resource "google_compute_url_map" "webpage_production" {
  name            = "trackrat-webpage-production-map"
  description     = "Consolidated LB: apiv2 -> API backend, apex/www -> webpage bucket"
  default_service = google_compute_backend_bucket.webpage_production_backend.id

  host_rule {
    hosts        = ["apiv2.trackrat.net"]
    path_matcher = "api"
  }

  path_matcher {
    name            = "api"
    default_service = data.google_compute_backend_service.api_production.id
  }
}

# SSL certificate covers both apex and www.
# NOTE: Google-managed certs cannot have their `domains` list changed in
# place — adding/removing a SAN requires creating a new cert resource.
resource "google_compute_managed_ssl_certificate" "webpage_production_cert" {
  name = "trackrat-webpage-production-cert"

  managed {
    domains = ["trackrat.net", "www.trackrat.net"]
  }
}

# Global static IP for production
resource "google_compute_global_address" "webpage_production_ip" {
  name = "trackrat-webpage-production-ip"
}

# HTTPS proxy for production. Serves two managed certs via SNI:
#   - webpage cert: trackrat.net, www.trackrat.net (owned here)
#   - API cert: apiv2.trackrat.net (owned by infra_v2/terraform/ production
#     workspace, referenced by self-link — both are already ACTIVE, so no
#     provisioning gap during cutover). Do not delete trackrat-production-cert
#     from the API workspace while it is attached here.
resource "google_compute_target_https_proxy" "webpage_production_proxy" {
  name    = "trackrat-webpage-production-https-proxy"
  url_map = google_compute_url_map.webpage_production.id
  ssl_certificates = [
    google_compute_managed_ssl_certificate.webpage_production_cert.id,
    "projects/${var.project_id}/global/sslCertificates/trackrat-production-cert",
  ]
}

# HTTPS forwarding rule for production
resource "google_compute_global_forwarding_rule" "webpage_production_https" {
  name       = "trackrat-webpage-production-https"
  target     = google_compute_target_https_proxy.webpage_production_proxy.id
  port_range = "443"
  ip_address = google_compute_global_address.webpage_production_ip.address
}

# HTTP to HTTPS redirect for production
resource "google_compute_url_map" "webpage_production_https_redirect" {
  name = "trackrat-webpage-production-https-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "PERMANENT_REDIRECT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "webpage_production_http_proxy" {
  name    = "trackrat-webpage-production-http-proxy"
  url_map = google_compute_url_map.webpage_production_https_redirect.id
}

resource "google_compute_global_forwarding_rule" "webpage_production_http" {
  name       = "trackrat-webpage-production-http-proxy-rule"
  target     = google_compute_target_http_proxy.webpage_production_http_proxy.id
  port_range = "80"
  ip_address = google_compute_global_address.webpage_production_ip.address
}

# Production outputs
output "production_webpage_ip" {
  value       = google_compute_global_address.webpage_production_ip.address
  description = "Point trackrat.net + www.trackrat.net DNS A records at this IP (Cloudflare: DNS only / grey-cloud)"
}

output "production_webpage_bucket" {
  value       = google_storage_bucket.webpage_production.name
  description = "Production GCS bucket name"
}

# ============================================
# Cloud Build triggers for webpage deployment
# ============================================
# Uses 2nd gen Cloud Build connection (trackrat-github) in us-east4.
# Triggers deploy webpage on branch push when webpage_v2/ files change.

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

  included_files = ["webpage_v2/**"]
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

  included_files = ["webpage_v2/**"]
  filename       = "infra_v2/cloudbuild-webpage.yaml"
}
