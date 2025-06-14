variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
}

variable "repository_name" {
  description = "Custom repository name (optional). If not provided, defaults to {app_name}-{environment}"
  type        = string
  default     = ""
}