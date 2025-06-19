variable "project_id" {
  description = "The GCP project ID for staging environment"
  type        = string
  default     = "trackrat-staging"
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
  default     = "staging"
}

variable "api_image_url" {
  description = "Docker image URL for the trackrat-api service"
  type        = string
  default     = "us-central1-docker.pkg.dev/trackrat-staging/trackcast-inference-staging/trackcast-inference:latest"
}

variable "enable_custom_domain" {
  description = "Enable custom domain mapping for the API service"
  type        = bool
  default     = true
}

variable "custom_domain_name" {
  description = "Custom domain name for the API service"
  type        = string
  default     = "staging.api.trackrat.net"
}

variable "critical_alert_email" {
  description = "Email address for critical database alerts"
  type        = string
  default     = "andy@andymartin.cc"
}

variable "warning_alert_email" {
  description = "Email address for warning database alerts"
  type        = string
  default     = "andy@andymartin.cc"
}