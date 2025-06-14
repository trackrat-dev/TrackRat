output "service_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.default.uri
}

output "service_name" {
  description = "Name of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.default.name
}

output "service_revision" {
  description = "Current revision of the Cloud Run service"
  value       = google_cloud_run_v2_service.default.latest_created_revision
}

output "service_account_email" {
  description = "Email of the service account used by the Cloud Run service"
  value       = local.effective_service_account_email
}

output "custom_domain_mapping_status" {
  description = "Status of the custom domain mapping. Includes resource records to be created in DNS."
  value       = var.enable_custom_domain && var.custom_domain_name != "" ? google_cloud_run_domain_mapping.default[0].status : null
}

output "custom_domain_name" {
  description = "The configured custom domain name."
  value       = var.enable_custom_domain && var.custom_domain_name != "" ? google_cloud_run_domain_mapping.default[0].name : null
}
