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