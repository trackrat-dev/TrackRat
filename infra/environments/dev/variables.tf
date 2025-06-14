variable "project_id" {
  description = "The GCP project ID for dev environment"
  type        = string
  default     = "trackrat-dev"
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-east1-b"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "trackrat"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "db_password" {
  description = "Database user password. This should be supplied via a secure method (e.g., .tfvars file not committed, or environment variable)."
  type        = string
  sensitive   = true
  # No default, should be provided per environment
}

variable "api_image_url" {
  description = "Docker image URL for the trackrat-api service"
  type        = string
  default     = "us-central1-docker.pkg.dev/trackrat-dev/trackcast-inference-dev/trackcast-inference:latest"
}

variable "vpc_connector_id" {
  description = "Self-link of the VPC Access Connector for Cloud Run"
  type        = string
  default     = null
}

variable "scheduler_image_url" {
  description = "Docker image URL for the trackrat-scheduler service in Dev"
  type        = string
  default     = "us-central1-docker.pkg.dev/trackrat-dev/trackcast-inference-dev/trackcast-inference:latest"
}