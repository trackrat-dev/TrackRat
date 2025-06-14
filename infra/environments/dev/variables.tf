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