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

# Database URL secret name is now output by the database module

output "njt_username_secret_name" {
  description = "Name of the NJ Transit username secret"
  value       = module.secrets.njt_username_secret_name
}

output "njt_password_secret_name" {
  description = "Name of the NJ Transit password secret"
  value       = module.secrets.njt_password_secret_name
}

output "njt_token_secret_name" {
  description = "Name of the NJ Transit token secret"
  value       = module.secrets.njt_token_secret_name
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = module.secrets.amtrak_api_key_secret_name
}

output "apns_team_id_secret_name" {
  description = "Name of the APNS Team ID secret"
  value       = module.secrets.apns_team_id_secret_name
}

output "apns_key_id_secret_name" {
  description = "Name of the APNS Key ID secret"
  value       = module.secrets.apns_key_id_secret_name
}


output "network_self_link" {
  description = "The self-link of the VPC network."
  value       = module.vpc.network_self_link
}

output "service_networking_connection" {
  description = "The service networking connection for private services"
  value       = module.vpc.service_networking_connection
}