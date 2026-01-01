# Simplified GCS + Load Balancer setup for Universal Links
# This version focuses on getting the core functionality working

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Variables
variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Random suffix for bucket name
resource "random_id" "bucket_suffix" {
  byte_length = 8
}

# Create the GCS bucket for Universal Links
resource "google_storage_bucket" "universal_links" {
  name          = "trackrat-links-${random_id.bucket_suffix.hex}"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true
  
  website {
    main_page_suffix = "index.html"
    not_found_page   = "train-fallback.html"
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Make bucket publicly readable
resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.universal_links.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Upload the Apple App Site Association file
resource "google_storage_bucket_object" "aasa" {
  name         = ".well-known/apple-app-site-association"
  bucket       = google_storage_bucket.universal_links.name
  source       = "apple-app-site-association"
  content_type = "application/json"
  
  cache_control = "public, max-age=3600"
}

# Upload the web fallback page
resource "google_storage_bucket_object" "fallback" {
  name         = "train-fallback.html"
  bucket       = google_storage_bucket.universal_links.name
  source       = "web-fallback.html"
  content_type = "text/html"
  
  cache_control = "public, max-age=300"
}

# Create backend service pointing to GCS bucket
resource "google_compute_backend_bucket" "universal_links_backend" {
  name        = "trackrat-links-backend"
  description = "Backend bucket for TrackRat Universal Links"
  bucket_name = google_storage_bucket.universal_links.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching  = true
  }
}

# Simple URL map - just serve from bucket
resource "google_compute_url_map" "universal_links" {
  name            = "trackrat-links-map"
  description     = "URL map for TrackRat Universal Links"
  default_service = google_compute_backend_bucket.universal_links_backend.id
}

# SSL certificate for trackrat.net
resource "google_compute_managed_ssl_certificate" "universal_links_cert" {
  name = "trackrat-links-cert"

  managed {
    domains = ["trackrat.net", "www.trackrat.net"]
  }
}

# Global static IP
resource "google_compute_global_address" "universal_links_ip" {
  name = "trackrat-links-ip"
}

# HTTPS proxy
resource "google_compute_target_https_proxy" "universal_links_proxy" {
  name             = "trackrat-links-https-proxy"
  url_map          = google_compute_url_map.universal_links.id
  ssl_certificates = [google_compute_managed_ssl_certificate.universal_links_cert.id]
}

# HTTPS forwarding rule
resource "google_compute_global_forwarding_rule" "universal_links_https" {
  name       = "trackrat-links-https"
  target     = google_compute_target_https_proxy.universal_links_proxy.id
  port_range = "443"
  ip_address = google_compute_global_address.universal_links_ip.address
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "https_redirect" {
  name = "trackrat-https-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "PERMANENT_REDIRECT"
    strip_query            = false
  }
}

# HTTP proxy for redirect
resource "google_compute_target_http_proxy" "universal_links_http_proxy" {
  name    = "trackrat-links-http-proxy"
  url_map = google_compute_url_map.https_redirect.id
}

# HTTP forwarding rule
resource "google_compute_global_forwarding_rule" "universal_links_http" {
  name       = "trackrat-links-http"
  target     = google_compute_target_http_proxy.universal_links_http_proxy.id
  port_range = "80"
  ip_address = google_compute_global_address.universal_links_ip.address
}

# Outputs
output "static_ip" {
  value       = google_compute_global_address.universal_links_ip.address
  description = "Point trackrat.net DNS A record to this IP"
}

output "bucket_name" {
  value       = google_storage_bucket.universal_links.name
  description = "GCS bucket name"
}

output "bucket_url" {
  value       = "https://storage.googleapis.com/${google_storage_bucket.universal_links.name}"
  description = "Direct bucket URL for testing"
}

output "test_urls" {
  value = {
    aasa_direct = "https://storage.googleapis.com/${google_storage_bucket.universal_links.name}/.well-known/apple-app-site-association"
    fallback_direct = "https://storage.googleapis.com/${google_storage_bucket.universal_links.name}/train-fallback.html"
    aasa_domain = "https://trackrat.net/.well-known/apple-app-site-association"
    train_domain = "https://trackrat.net/train-fallback.html"
  }
  description = "URLs to test (direct = immediate, domain = after DNS setup)"
}