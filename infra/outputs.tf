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

output "secret_manager_secret_name" {
  description = "Name of the Secret Manager secret"
  value       = module.secrets.secret_name
}