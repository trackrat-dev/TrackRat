# Load Balancer Configuration
# HTTPS load balancer with managed SSL certificate

# Static IP address
resource "google_compute_global_address" "trackrat" {
  name    = "trackrat-${var.environment}-ip"
  project = var.project_id

  depends_on = [google_project_service.apis]
}

# Managed SSL certificate
resource "google_compute_managed_ssl_certificate" "trackrat" {
  name = "trackrat-${var.environment}-cert"

  managed {
    domains = [var.domain]
  }

  depends_on = [google_project_service.apis]
}

# Backend service
resource "google_compute_backend_service" "trackrat" {
  name                  = "trackrat-${var.environment}-backend"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 300
  health_checks         = [google_compute_health_check.trackrat.id]
  load_balancing_scheme = "EXTERNAL"

  backend {
    group           = google_compute_instance_group_manager.trackrat.instance_group
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }

  depends_on = [google_compute_instance_group_manager.trackrat]
}

# URL map
resource "google_compute_url_map" "trackrat" {
  name            = "trackrat-${var.environment}-urlmap"
  default_service = google_compute_backend_service.trackrat.id

  depends_on = [google_compute_backend_service.trackrat]
}

# HTTPS proxy
resource "google_compute_target_https_proxy" "trackrat" {
  name             = "trackrat-${var.environment}-https-proxy"
  url_map          = google_compute_url_map.trackrat.id
  ssl_certificates = [google_compute_managed_ssl_certificate.trackrat.id]

  depends_on = [
    google_compute_url_map.trackrat,
    google_compute_managed_ssl_certificate.trackrat,
  ]
}

# HTTPS forwarding rule
resource "google_compute_global_forwarding_rule" "trackrat_https" {
  name                  = "trackrat-${var.environment}-https"
  ip_address            = google_compute_global_address.trackrat.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.trackrat.id
  load_balancing_scheme = "EXTERNAL"

  depends_on = [google_compute_target_https_proxy.trackrat]
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "trackrat_redirect" {
  name = "trackrat-${var.environment}-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "trackrat_redirect" {
  name    = "trackrat-${var.environment}-http-proxy"
  url_map = google_compute_url_map.trackrat_redirect.id
}

resource "google_compute_global_forwarding_rule" "trackrat_http" {
  name                  = "trackrat-${var.environment}-http"
  ip_address            = google_compute_global_address.trackrat.address
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.trackrat_redirect.id
  load_balancing_scheme = "EXTERNAL"
}
