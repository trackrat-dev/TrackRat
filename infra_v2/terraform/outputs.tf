# Outputs

output "load_balancer_ip" {
  description = "External IP of the load balancer"
  value       = google_compute_global_address.trackrat.address
}

output "api_url" {
  description = "URL for the API"
  value       = "https://${var.domain}"
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
