# TrackRat V2 Variables

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "trackrat-v2"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-east4"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-east4-a"
}

variable "environment" {
  description = "Environment name (staging or production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

variable "domain" {
  description = "Domain for the API - defaults based on environment (staging.apiv2.trackrat.net or apiv2.trackrat.net)"
  type        = string
  default     = "" # Empty means use local.domain
}

variable "machine_type" {
  description = "GCE machine type"
  type        = string
  default     = "t2d-standard-1"
}

variable "disk_size_gb" {
  description = "Persistent disk size in GB"
  type        = number
  default     = 20
}

variable "snapshot_retention_days" {
  description = "Number of days to retain disk snapshots"
  type        = number
  default     = 35
}

variable "alert_email" {
  description = "Email address for uptime monitoring alerts"
  type        = string
  default     = "andymartin11@gmail.com"
}
