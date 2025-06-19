variable "project_id" {
  description = "The GCP project ID for dev environment"
  type        = string
  default     = "trackrat-dev"
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-central1-b"
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

# db_password is now auto-generated in the database module

variable "api_image_url" {
  description = "Docker image URL for the trackrat-api service"
  type        = string
  default     = "us-central1-docker.pkg.dev/trackrat-dev/trackcast-inference-dev/trackcast-inference:latest"
}

variable "enable_custom_domain" {
  description = "Enable custom domain mapping for the API service"
  type        = bool
  default     = true
}

variable "custom_domain_name" {
  description = "Custom domain name for the API service"
  type        = string
  default     = "dev.api.trackrat.net"
}



