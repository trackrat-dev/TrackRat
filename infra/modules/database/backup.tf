# This file is intended for managing specific backup policies and schedules
# for the Cloud SQL instances.
# The primary backup configuration (enablement, PITR, retention) is defined
# within the google_sql_database_instance resource in main.tf.

# If you need to define a specific start time for the daily backup window,
# you can use the variable below and reference it in the
# settings.backup_configuration.start_time attribute in main.tf.

# variable "backup_window_start_time" {
#   description = "The start time of the daily backup window, in HH:MM format (UTC). Example: '03:00'."
#   type        = string
#   default     = null # Setting to null means GCP will choose a default window.
# }

# Example usage in main.tf inside settings.backup_configuration:
#   start_time = var.backup_window_start_time != null ? var.backup_window_start_time : null
