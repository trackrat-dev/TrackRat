# Outputs

output "api_url" {
  description = "Public URL clients use to reach the API. Both environments are fronted by a Cloudflare Tunnel; staging's hostname is staging-api.trackrat.net — see the locals block in main.tf."
  value       = "https://${var.domain != "" ? var.domain : local.public_api_domain}"
}

output "mig_name" {
  description = "Name of the managed instance group"
  value       = google_compute_instance_group_manager.trackrat.name
}

output "service_account_email" {
  description = "Service account email for the VMs"
  value       = google_service_account.trackrat.email
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for container images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.trackrat.name}"
}

output "deploy_bucket" {
  description = "GCS bucket for deployment artifacts"
  value       = google_storage_bucket.deploy.name
}
