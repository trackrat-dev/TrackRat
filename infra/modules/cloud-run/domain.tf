resource "google_cloud_run_domain_mapping" "default" {
  count    = var.enable_custom_domain && var.custom_domain_name != "" ? 1 : 0
  project  = var.project_id
  location = var.location
  name     = var.custom_domain_name

  spec {
    route_name = google_cloud_run_v2_service.default.name
    # certificate_mode = "AUTOMATIC" # Default is AUTOMATIC
    force_override = true
  }

  depends_on = [google_cloud_run_v2_service.default]
}
