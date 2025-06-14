variable "project_id" {
  description = "The GCP project ID for staging environment"
  type        = string
  default     = "trackrat-staging"
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

variable "api_image_url_staging" {
  description = "Docker image URL for the trackrat-api service in Staging"
  type        = string
}

variable "vpc_connector_id_staging" {
  description = "Self-link of the VPC Access Connector for Cloud Run in Staging"
  type        = string
}

variable "scheduler_image_url_staging" {
  description = "Docker image URL for the trackrat-scheduler service in Staging"
  type        = string
}