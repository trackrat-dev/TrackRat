variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "location" {
  description = "The GCP region for Cloud Run services"
  type        = string
}

variable "service_name" {
  description = "Name of the Collector Cloud Run service"
  type        = string
  default     = "trackrat-collector"
}

variable "container_image" {
  description = "Docker image URL for the collector service"
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
  default     = "1" // Default, can be adjusted based on workload
}

variable "memory_limit" {
  description = "Memory limit for the container"
  type        = string
  default     = "2Gi" // Updated to 2GB for consistency
}

variable "min_instances" {
  description = "Minimum number of instances for the collector service"
  type        = number
  default     = 0 // Can scale to 0
}

variable "max_instances" {
  description = "Maximum number of instances for the collector service"
  type        = number
  default     = 5 // Allow some concurrency, adjust as needed
}

variable "concurrency_per_instance" {
  description = "Number of concurrent messages/requests per instance"
  type        = number
  default     = 10 // Adjust based on how heavy message processing is
}

variable "request_timeout_seconds" {
  description = "Request timeout in seconds for message processing"
  type        = number
  default     = 300 // 5 minutes, adjust based on expected processing time
}

variable "collector_service_account_email" {
  description = "Service account email for the Cloud Run service. If null, one is created."
  type        = string
  default     = null
}

variable "pubsub_topic_name" {
  description = "Name of the existing Pub/Sub topic to subscribe to (just the name, not full path)."
  type        = string
}

variable "pubsub_subscription_name" {
  description = "Name for the Pub/Sub subscription."
  type        = string
  default     = "" # If empty, will be auto-generated
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

variable "ack_deadline_seconds" {
  description = "The acknowledgment deadline for Pub/Sub messages."
  type        = number
  default     = 60 // Default is 10s, increase if processing takes longer but less than timeout
}

variable "retry_policy" {
  description = "Pub/Sub subscription retry policy. Object with 'minimum_backoff' and 'maximum_backoff'."
  type = object({
    minimum_backoff = optional(string, "10s")
    maximum_backoff = optional(string, "600s")
  })
  default = {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}
