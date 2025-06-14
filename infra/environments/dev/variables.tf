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

variable "db_password" {
  description = "Database user password. This should be supplied via a secure method (e.g., .tfvars file not committed, or environment variable)."
  type        = string
  sensitive   = true
  # No default, should be provided per environment
}