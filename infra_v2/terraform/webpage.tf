# TrackRat Webpage Infrastructure
#
# Staging webpage: GCS bucket + CDN + LB for staging.trackrat.net
# Production webpage (trackrat.net): lives in GCP project trackrat-prod,
# managed separately outside this Terraform config.
#
# Cloud Build triggers for both staging and production webpage deployments.
#
# NOTE: This config was previously in universal-links-deployment/gcs-simple-setup.tf
# with its own local Terraform state. If importing existing resources into this
# workspace, run:
#   terraform import google_storage_bucket.webpage_staging trackrat-webpage-staging
#   terraform import google_storage_bucket_iam_member.staging_public_access \
#     "trackrat-webpage-staging roles/storage.objectViewer allUsers"
#   terraform import google_compute_backend_bucket.webpage_staging_backend \
#     projects/${var.project_id}/global/backendBuckets/trackrat-webpage-staging-backend
#   terraform import google_compute_url_map.webpage_staging \
#     projects/${var.project_id}/global/urlMaps/trackrat-webpage-staging-map
#   terraform import google_compute_managed_ssl_certificate.webpage_staging_cert \
#     projects/${var.project_id}/global/sslCertificates/trackrat-webpage-staging-cert
#   terraform import google_compute_global_address.webpage_staging_ip \
#     projects/${var.project_id}/global/addresses/trackrat-webpage-staging-ip
#   terraform import google_compute_target_https_proxy.webpage_staging_proxy \
#     projects/${var.project_id}/global/targetHttpsProxies/trackrat-webpage-staging-https-proxy
#   terraform import google_compute_global_forwarding_rule.webpage_staging_https \
#     projects/${var.project_id}/global/forwardingRules/trackrat-webpage-staging-https
#   terraform import google_compute_url_map.webpage_staging_https_redirect \
#     projects/${var.project_id}/global/urlMaps/trackrat-webpage-staging-https-redirect
#   terraform import google_compute_target_http_proxy.webpage_staging_http_proxy \
#     projects/${var.project_id}/global/targetHttpProxies/trackrat-webpage-staging-http-proxy
#   terraform import google_compute_global_forwarding_rule.webpage_staging_http \
#     projects/${var.project_id}/global/forwardingRules/trackrat-webpage-staging-http
#   terraform import google_cloudbuild_trigger.webpage_staging \
#     projects/${var.project_id}/locations/us-east4/triggers/trackrat-webpage-staging
#   terraform import google_cloudbuild_trigger.webpage_production \
#     projects/${var.project_id}/locations/us-east4/triggers/trackrat-webpage-production

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
    repository = "projects/${var.project_id}/locations/us-east4/connections/trackrat-github/repositories/TrackRat"
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
    repository = "projects/${var.project_id}/locations/us-east4/connections/trackrat-github/repositories/TrackRat"
    push {
      branch = "^production$"
    }
  }

  included_files = ["webpage_v2/**"]
  filename       = "infra_v2/cloudbuild-webpage.yaml"
}
