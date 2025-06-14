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

variable "db_password" {
  description = "Database user password for staging. Supplied via secure method."
  type        = string
  sensitive   = true
  # No default
}