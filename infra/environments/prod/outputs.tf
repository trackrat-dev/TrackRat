output "project_id" {
  description = "GCP project ID"
  value       = module.infrastructure.project_id
}

output "region" {
  description = "GCP region"
  value       = module.infrastructure.region
}

output "vpc_network_name" {
  description = "Name of the VPC network"
  value       = module.infrastructure.vpc_network_name
}

output "vpc_subnet_name" {
  description = "Name of the VPC subnet"
  value       = module.infrastructure.vpc_subnet_name
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository for Docker images"
  value       = module.infrastructure.artifact_registry_repository
}

output "secret_manager_secret_name" {
  description = "Name of the Secret Manager secret"
  value       = module.infrastructure.secret_manager_secret_name
}

output "trackrat_api_service_url_prod" {
  description = "URL of the trackrat-api service in production"
  value       = module.trackrat_api_service_prod.service_url
}

output "trackrat_api_custom_domain_name_prod" {
  description = "Custom domain name for the trackrat-api service in production"
  value       = module.trackrat_api_service_prod.custom_domain_name
  sensitive   = true
}

output "trackrat_scheduler_service_url_prod" {
  description = "URL of the trackrat-scheduler service in production"
  value       = module.trackrat_scheduler_prod.scheduler_cloud_run_service_url
}

output "trackrat_scheduler_job_name_prod" {
  description = "Name of the Cloud Scheduler job for the production environment"
  value       = module.trackrat_scheduler_prod.scheduler_job_name
}