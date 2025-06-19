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

output "database_url_secret_name" {
  description = "Name of the database URL secret"
  value       = module.database.database_url_secret_name
}

output "njt_username_secret_name" {
  description = "Name of the NJ Transit username secret"
  value       = module.infrastructure.njt_username_secret_name
}

output "njt_password_secret_name" {
  description = "Name of the NJ Transit password secret"
  value       = module.infrastructure.njt_password_secret_name
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = module.infrastructure.amtrak_api_key_secret_name
}

output "trackrat_api_service_url" {
  description = "URL of the trackrat-api service in staging"
  value       = module.trackrat_api_service.service_url
}

output "trackrat_api_custom_domain_name" {
  description = "Custom domain name for the trackrat-api service in staging"
  value       = module.trackrat_api_service.custom_domain_name
}

output "trackrat_api_custom_domain_mapping_status" {
  description = "Status of the custom domain mapping for the trackrat-api service"
  value       = module.trackrat_api_service.custom_domain_mapping_status
}

output "scheduler_job_names" {
  description = "Names of the Cloud Scheduler jobs in staging"
  value       = [for job in google_cloud_scheduler_job.operations : job.name]
}

output "scheduler_service_account_email" {
  description = "Email of the service account used by scheduler jobs"
  value       = google_service_account.scheduler_sa.email
}

# Database connection outputs for automated secret management
output "database_private_ip" {
  description = "Private IP of the database instance"
  value       = module.database.private_ip_address
}

output "database_name" {
  description = "Name of the database"
  value       = module.database.database_name
}

output "database_user_name" {
  description = "Database user name"
  value       = module.database.database_user_name
}

output "database_password_secret_id" {
  description = "Secret Manager secret ID for database password"
  value       = module.database.db_password_secret_id
}

output "app_secrets_name" {
  description = "Name of the main application secrets"
  value       = "trackrat-staging-secrets"
}