variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "location" {
  description = "The GCP region for Cloud Run services"
  type        = string
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "container_image" {
  description = "Docker image URL for the service"
  type        = string
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

variable "cpu_limit" {
  description = "CPU limit for the container (e.g., '1', '2')"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for the container (e.g., '512Mi', '1Gi')"
  type        = string
  default     = "2Gi"
}

variable "concurrency" {
  description = "Number of concurrent requests per instance"
  type        = number
  default     = 80 # Default is 80, issue asks for 100 for API
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 2 # As per issue spec
}

variable "request_timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 60 # As per issue spec
}

variable "environment_variables" {
  description = "A map of environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "A map of environment variables to be sourced from Secret Manager. Key is the env var name, value is the secret name:version."
  type        = map(string)
  default     = {}
}

variable "vpc_connector_id" {
  description = "ID of the VPC Access Connector (self_link) for private IP access to Cloud SQL. Null if not needed."
  type        = string
  default     = null
}

variable "enable_cloudsql_access" {
  description = "Whether to grant Cloud SQL client permissions to the service account"
  type        = bool
  default     = false
}

variable "startup_probe_path" {
  description = "Path for the startup probe (e.g., /healthz). Disabled if null."
  type        = string
  default     = "/health" # As per issue spec
}

variable "startup_probe_initial_delay_seconds" {
  description = "Initial delay for startup probe in seconds"
  type        = number
  default     = 0
}

variable "startup_probe_timeout_seconds" {
  description = "Timeout for startup probe in seconds"
  type        = number
  default     = 5
}

variable "startup_probe_period_seconds" {
  description = "Period for startup probe in seconds"
  type        = number
  default     = 10
}

variable "startup_probe_failure_threshold" {
  description = "Failure threshold for startup probe"
  type        = number
  default     = 60
}

variable "liveness_probe_path" {
  description = "Path for the liveness probe. Disabled if null."
  type        = string
  default     = "/health" # Assuming same as startup, can be configured
}

variable "liveness_probe_period_seconds" {
  description = "Periodicity of liveness probe in seconds."
  type        = number
  default     = 30 # As per issue spec
}

variable "service_account_email" {
  description = "Email of the service account to run the service as. If null, a new one will be created."
  type        = string
  default     = null
}

variable "enable_custom_domain" {
  description = "Set to true to enable custom domain mapping"
  type        = bool
  default     = false
}

variable "custom_domain_name" {
  description = "The custom domain name (e.g., api.example.com)"
  type        = string
  default     = ""
}


variable "labels" {
  description = "A map of labels to apply to the service."
  type        = map(string)
  default     = {}
}

variable "annotations" {
  description = "A map of annotations to apply to the service."
  type        = map(string)
  default     = {}
}
