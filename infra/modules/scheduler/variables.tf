variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "location" {
  description = "The GCP region for Cloud Run services and Scheduler"
  type        = string
}

variable "service_name" {
  description = "Name of the Scheduler Cloud Run service"
  type        = string
  default     = "trackrat-scheduler"
}

variable "container_image" {
  description = "Docker image URL for the scheduler service"
  type        = string
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

variable "cpu_limit" {
  description = "CPU limit for the container"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for the container"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0 # Can be 0 for non-prod, 1 for prod if needed for readiness
}

variable "max_instances" {
  description = "Maximum number of instances (must be 1 for this service)"
  type        = number
  default     = 1
}

variable "request_timeout_seconds" {
  description = "Request timeout in seconds (up to 3600 for Cloud Run v2, issue asks for 60 mins)"
  type        = number
  default     = 3600 # 60 minutes
}

variable "scheduler_service_account_email" {
  description = "Service account email for the Cloud Run service. If null, one is created."
  type        = string
  default     = null
}

variable "scheduler_job_name" {
  description = "Name for the Cloud Scheduler job"
  type        = string
  default     = "invoke-trackrat-scheduler"
}

variable "scheduler_job_description" {
  description = "Description for the Cloud Scheduler job"
  type        = string
  default     = "Triggers the TrackRat Scheduler service"
}

variable "scheduler_schedule" {
  description = "Cron schedule for the job (e.g., '0 * * * *' for hourly)"
  type        = string
}

variable "scheduler_timezone" {
  description = "Timezone for the scheduler job"
  type        = string
  default     = "Etc/UTC"
}


variable "scheduler_job_service_account_email" {
  description = "Service account email for the Cloud Scheduler job to invoke the Cloud Run service. If null, one is created."
  type        = string
  default     = null # This SA will need roles/run.invoker for the scheduler Cloud Run service
}

variable "environment_variables" {
  description = "A map of environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "A map of environment variables to be sourced from Secret Manager."
  type        = map(string)
  default     = {}
}

variable "vpc_connector_id" {
  description = "ID of the VPC Access Connector. Null if not needed."
  type        = string
  default     = null
}

variable "labels" {
  description = "A map of labels to apply to the service."
  type        = map(string)
  default     = {}
}
