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