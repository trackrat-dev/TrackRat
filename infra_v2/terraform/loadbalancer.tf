# Load Balancer Configuration
# HTTPS load balancer with managed SSL certificate.
#
# The backend service and managed SSL certificate below always exist. Once
# var.consolidate_api_lb is flipped (runbook Phase 4), PRODUCTION's HTTPS
# *frontend* (static IP, url map, proxies, forwarding rules) is no longer
# created here — apiv2.trackrat.net is served by the consolidated webpage
# load balancer (infra_v2/terraform-webpage), which host-routes it to this
# backend service (by name) and attaches this cert (by self-link). That
# consolidation removes production's 2 dedicated global forwarding rules.
# STAGING always keeps its own dedicated frontend.

# Managed SSL certificate (referenced by the consolidated webpage proxy in
# production via self-link "projects/<project>/global/sslCertificates/trackrat-production-cert").
resource "google_compute_managed_ssl_certificate" "trackrat" {
  name = "trackrat-${var.environment}-cert"

  managed {
    domains = [var.domain != "" ? var.domain : local.domain]
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Staging webpage serving (consolidated onto this API LB — staging only).
# The staging webpage bucket (trackrat-webpage-staging) is owned by the
# infra_v2/terraform-webpage root; here we only add the LB pieces needed to
# serve it at staging.trackrat.net through the existing staging frontend: a
# CDN-backed backend bucket, a managed cert (attached to the HTTPS proxy via
# SNI alongside the apiv2 cert), and a host rule on the url map below. Mirrors
# production's consolidated LB, minus the apex HSTS/preload header (never
# preload a staging subdomain).
# ---------------------------------------------------------------------------

# Managed SSL certificate for the staging webpage host.
resource "google_compute_managed_ssl_certificate" "webpage_staging" {
  count = local.serve_webpage_on_api_lb ? 1 : 0
  name  = "trackrat-webpage-staging-cert"

  managed {
    domains = [local.webpage_staging_domain]
  }

  depends_on = [google_project_service.apis]
}

# CDN backend bucket wrapping the staging webpage GCS bucket.
resource "google_compute_backend_bucket" "webpage_staging" {
  count       = local.serve_webpage_on_api_lb ? 1 : 0
  name        = "trackrat-webpage-staging-backend"
  description = "Backend bucket for TrackRat staging webpage"
  bucket_name = local.webpage_staging_bucket
  enable_cdn  = true

  cdn_policy {
    cache_mode       = "CACHE_ALL_STATIC"
    default_ttl      = 3600  # 1 hour fallback (objects' own Cache-Control wins)
    max_ttl          = 86400 # 24 hours
    client_ttl       = 3600
    negative_caching = true
  }
}

# Backend service (referenced by the consolidated webpage url map in production
# via a google_compute_backend_service data source keyed on this stable name).
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

# ---------------------------------------------------------------------------
# Dedicated HTTPS frontend — gated on local.create_api_frontend (true in
# staging always; true in production until var.consolidate_api_lb flips at
# runbook Phase 4, after which the webpage LB serves apiv2).
#
# The moved blocks record the no-count -> count refactor so existing state
# maps to [0] instead of destroy/create. Terraform >= 1.1 implies these moves
# for the count boundary automatically, but stating them makes the plan
# guarantee explicit: while create_api_frontend is true, a plan against
# existing state must show zero frontend destroys.
# ---------------------------------------------------------------------------

moved {
  from = google_compute_global_address.trackrat
  to   = google_compute_global_address.trackrat[0]
}

moved {
  from = google_compute_url_map.trackrat
  to   = google_compute_url_map.trackrat[0]
}

moved {
  from = google_compute_target_https_proxy.trackrat
  to   = google_compute_target_https_proxy.trackrat[0]
}

moved {
  from = google_compute_global_forwarding_rule.trackrat_https
  to   = google_compute_global_forwarding_rule.trackrat_https[0]
}

moved {
  from = google_compute_url_map.trackrat_redirect
  to   = google_compute_url_map.trackrat_redirect[0]
}

moved {
  from = google_compute_target_http_proxy.trackrat_redirect
  to   = google_compute_target_http_proxy.trackrat_redirect[0]
}

moved {
  from = google_compute_global_forwarding_rule.trackrat_http
  to   = google_compute_global_forwarding_rule.trackrat_http[0]
}

# Static IP address
resource "google_compute_global_address" "trackrat" {
  count   = local.create_api_frontend ? 1 : 0
  name    = "trackrat-${var.environment}-ip"
  project = var.project_id

  depends_on = [google_project_service.apis]
}

# URL map. Default host (staging.apiv2.trackrat.net) -> API backend. In staging,
# staging.trackrat.net is host-routed to the webpage backend bucket.
resource "google_compute_url_map" "trackrat" {
  count           = local.create_api_frontend ? 1 : 0
  name            = "trackrat-${var.environment}-urlmap"
  default_service = google_compute_backend_service.trackrat.id

  dynamic "host_rule" {
    for_each = local.serve_webpage_on_api_lb ? [1] : []
    content {
      hosts        = [local.webpage_staging_domain]
      path_matcher = "webpage"
    }
  }

  dynamic "path_matcher" {
    for_each = local.serve_webpage_on_api_lb ? [1] : []
    content {
      name            = "webpage"
      default_service = google_compute_backend_bucket.webpage_staging[0].id
    }
  }

  depends_on = [google_compute_backend_service.trackrat]
}

# HTTPS proxy. Serves the apiv2 cert always, plus the staging webpage cert via
# SNI when the webpage is consolidated onto this LB (mirrors production's proxy,
# which serves the webpage + apiv2 certs together).
resource "google_compute_target_https_proxy" "trackrat" {
  count   = local.create_api_frontend ? 1 : 0
  name    = "trackrat-${var.environment}-https-proxy"
  url_map = google_compute_url_map.trackrat[0].id
  ssl_certificates = concat(
    [google_compute_managed_ssl_certificate.trackrat.id],
    local.serve_webpage_on_api_lb ? [google_compute_managed_ssl_certificate.webpage_staging[0].id] : [],
  )

  depends_on = [
    google_compute_url_map.trackrat,
    google_compute_managed_ssl_certificate.trackrat,
  ]
}

# HTTPS forwarding rule
resource "google_compute_global_forwarding_rule" "trackrat_https" {
  count                 = local.create_api_frontend ? 1 : 0
  name                  = "trackrat-${var.environment}-https"
  ip_address            = google_compute_global_address.trackrat[0].address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.trackrat[0].id
  load_balancing_scheme = "EXTERNAL"

  depends_on = [google_compute_target_https_proxy.trackrat]
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "trackrat_redirect" {
  count = local.create_api_frontend ? 1 : 0
  name  = "trackrat-${var.environment}-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "trackrat_redirect" {
  count   = local.create_api_frontend ? 1 : 0
  name    = "trackrat-${var.environment}-http-proxy"
  url_map = google_compute_url_map.trackrat_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "trackrat_http" {
  count                 = local.create_api_frontend ? 1 : 0
  name                  = "trackrat-${var.environment}-http"
  ip_address            = google_compute_global_address.trackrat[0].address
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.trackrat_redirect[0].id
  load_balancing_scheme = "EXTERNAL"
}
