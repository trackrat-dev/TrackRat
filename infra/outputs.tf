output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP region"
  value       = var.region
}

output "vpc_network_name" {
  description = "Name of the VPC network"
  value       = module.vpc.network_name
}

output "vpc_subnet_name" {
  description = "Name of the VPC subnet"
  value       = module.vpc.subnet_name
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository for Docker images"
  value       = module.artifact_registry.repository_id
}

output "database_url_secret_name" {
  description = "Name of the database URL secret"
  value       = module.secrets.database_url_secret_name
}

output "njt_username_secret_name" {
  description = "Name of the NJ Transit username secret"
  value       = module.secrets.njt_username_secret_name
}

output "njt_password_secret_name" {
  description = "Name of the NJ Transit password secret"
  value       = module.secrets.njt_password_secret_name
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = module.secrets.amtrak_api_key_secret_name
}

output "network_self_link" {
  description = "The self-link of the VPC network."
  value       = module.vpc.network_self_link
}