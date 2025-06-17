variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "location" {
  description = "GCP region where jobs will be created"
  type        = string
}

variable "job_name_prefix" {
  description = "Prefix for job names (e.g., 'trackrat-ops')"
  type        = string
}

variable "container_image" {
  description = "Docker image to use for the jobs"
  type        = string
}

variable "jobs" {
  description = "Map of job configurations"
  type = map(object({
    command               = list(string)              # Command to execute
    args                  = optional(list(string))    # Command arguments
    cpu_limit             = optional(string, "1")     # CPU limit (e.g., "1", "2", "4")
    memory_limit          = optional(string, "2Gi")   # Memory limit (e.g., "512Mi", "1Gi", "2Gi")
    max_retries           = optional(number, 3)       # Max retries on failure
    task_timeout          = optional(string, "300s")  # Task timeout
    environment_variables = optional(map(string), {}) # Job-specific env vars
  }))

  validation {
    condition = alltrue([
      for job_name, job_config in var.jobs :
      length(job_config.command) > 0
    ])
    error_message = "Each job must have at least one command specified."
  }
}

variable "service_account_email" {
  description = "Service account email for job execution"
  type        = string
}

variable "vpc_connector_id" {
  description = "VPC connector for private network access (optional)"
  type        = string
  default     = null
}

variable "environment_variables" {
  description = "Environment variables to set for all jobs"
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "Secret environment variables from Secret Manager (format: secret_name:version)"
  type        = map(string)
  default     = {}
}

variable "labels" {
  description = "Labels to apply to all jobs"
  type        = map(string)
  default     = {}
}