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

variable "api_image_url" {
  description = "Docker image URL for the trackrat-api service"
  type        = string
  # default   = "us-central1-docker.pkg.dev/your-project-id/trackrat-repo/trackrat-api:latest" # Example, replace
}

variable "vpc_connector_id" {
  description = "Self-link of the VPC Access Connector for Cloud Run"
  type        = string
  # default   = "projects/your-project-id/locations/us-central1/connectors/your-connector-name" # Example, replace
}

variable "scheduler_image_url" {
  description = "Docker image URL for the trackrat-scheduler service in Dev"
  type        = string
  # default   = "us-central1-docker.pkg.dev/your-project-id/trackrat-repo/trackrat-scheduler:latest" # Example
}