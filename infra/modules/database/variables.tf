variable "project_id" {
  description = "The ID of the Google Cloud project."
  type        = string
}

variable "region" {
  description = "The region for the Cloud SQL instance."
  type        = string
}

variable "instance_name" {
  description = "The name of the Cloud SQL instance."
  type        = string
  default     = "trackrat-db-instance"
}

variable "database_version" {
  description = "The version of PostgreSQL to use (e.g., POSTGRES_15)."
  type        = string
  default     = "POSTGRES_15"
}

variable "instance_tier" {
  description = "The machine type for the Cloud SQL instance (e.g., db-custom-2-7680)."
  type        = string
  default     = "db-g1-small" # 1.7GB memory, 1 shared core
}

variable "network_self_link" {
  description = "The self-link of the VPC network to attach the Cloud SQL instance to."
  type        = string
}

variable "service_networking_connection" {
  description = "The service networking connection for private services (used for dependency)"
  type        = any
  default     = null
}

variable "maintenance_window_day" {
  description = "The day of the week for the maintenance window (1-7, Monday-Sunday)."
  type        = number
  default     = 7 # Sunday
}

variable "maintenance_window_hour" {
  description = "The hour of the day (UTC) for the maintenance window (0-23)."
  type        = number
  default     = 6 # 6 AM UTC
}

variable "database_name" {
  description = "The name of the database to create."
  type        = string
  default     = "trackratdb"
}

variable "database_user_name" {
  description = "The name of the database user."
  type        = string
  default     = "trackratuser"
}

# database_user_password is now auto-generated using random_password resource

variable "deletion_protection" {
  description = "Whether or not to enable deletion protection for the instance."
  type        = bool
  default     = false # Recommended to be true for production
}

# Variables from backup.tf (conceptual, as actual var is here)
variable "backup_window_start_time" {
  description = "The start time of the daily backup window, in HH:MM format (UTC). Example: '03:00'. If null, GCP chooses a default."
  type        = string
  default     = "03:00" # Example default
}

# Variables for monitoring flags (from monitoring.tf)

variable "slow_query_log_min_duration" {
  description = "Minimum query duration in ms to be logged as a slow query. Use 0 to disable. For PostgreSQL, this is 'log_min_duration_statement'."
  type        = number
  default     = 500 # ms
}

variable "log_connections" {
  description = "Log connections to the database (flag: log_connections)."
  type        = bool
  default     = false # Can be verbose, enable with caution
}

variable "log_disconnections" {
  description = "Log disconnections from the database (flag: log_disconnections)."
  type        = bool
  default     = false # Can be verbose, enable with caution
}

variable "max_connections_limit" {
  description = "The maximum number of concurrent connections for the database (flag: max_connections). Default depends on instance size."
  type        = number
  default     = 100 # Set a sensible default, actual max depends on tier.
}


# Variables for monitoring alerts (from monitoring.tf)
variable "cpu_alert_threshold_percent" {
  description = "CPU utilization percentage threshold for alerting."
  type        = number
  default     = 80
}

variable "memory_alert_threshold_gb" {
  description = "Available memory threshold in GB for alerting."
  type        = number
  default     = 1.4 # Alert if less than 1.4GB available (adjusted for 1.7GB instance)
}

# Removed unused variables: enable_read_replica, replica_lag_alert_threshold_seconds, active_connections_alert_threshold
# These variables are for future replica and connection monitoring features

# TODO: Add variables for notification channel IDs for alerts
# variable "notification_channel_email" {
#   description = "Monitoring notification channel ID for email."
#   type        = string
#   default     = "" # Needs to be configured in the root/env level
# }
