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

output "njt_token_secret_name" {
  description = "Name of the NJ Transit API token secret"
  value       = module.infrastructure.njt_token_secret_name
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = module.infrastructure.amtrak_api_key_secret_name
}

output "trackrat_api_service_url" {
  description = "URL of the trackrat-api service in production"
  value       = module.trackrat_api_service.service_url
}

output "trackrat_api_custom_domain_name" {
  description = "Custom domain name for the trackrat-api service in production"
  value       = module.trackrat_api_service.custom_domain_name
}

output "trackrat_api_custom_domain_mapping_status" {
  description = "Status of the custom domain mapping for the trackrat-api service"
  value       = module.trackrat_api_service.custom_domain_mapping_status
}

output "database_url_secret_name" {
  description = "Name of the database URL secret in Secret Manager"
  value       = module.infrastructure.database_url_secret_name
}

output "app_secrets_name" {
  description = "Name of the main application secrets"
  value       = "trackrat-prod-secrets"
}
