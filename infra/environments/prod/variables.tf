variable "project_id" {
  description = "The GCP project ID for production environment"
  type        = string
  default     = "trackrat-prod"
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

variable "api_image_url_prod" {
  description = "Docker image URL for the trackrat-api service in Production"
  type        = string
}

variable "vpc_connector_id_prod" {
  description = "Self-link of the VPC Access Connector for Cloud Run in Production"
  type        = string
}

variable "scheduler_image_url_prod" {
  description = "Docker image URL for the trackrat-scheduler service in Production"
  type        = string
}