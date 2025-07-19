variable "project_id" {
  description = "The GCP project ID for production environment"
  type        = string
  default     = "trackrat-prod"
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

variable "api_image_url" {
  description = "Docker image URL for the trackrat-api service"
  type        = string
  default     = "us-central1-docker.pkg.dev/trackrat-prod/trackcast-inference-prod/trackcast-inference:latest"
}

variable "enable_custom_domain" {
  description = "Enable custom domain mapping for the API service"
  type        = bool
  default     = true
}

variable "custom_domain_name" {
  description = "Custom domain name for the API service"
  type        = string
  default     = "prod.api.trackrat.net"
}

