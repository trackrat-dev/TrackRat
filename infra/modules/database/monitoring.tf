# This file is intended for managing database metrics, logging, and alerts.

# To enable Cloud SQL Insights and other logging, specific database flags
# need to be set on the Cloud SQL instance. These flags are defined in main.tf
# within the settings.database_flags block. We will add variables for these flags
# and instruct the user to set them in variables.tf / environment .tfvars.

# Example flags for monitoring (to be added in main.tf and defined in variables.tf):
# variable "enable_cloud_sql_insights" {
#   description = "Enable Cloud SQL Insights (Query Insights)."
#   type        = bool
#   default     = true
# }
# variable "slow_query_log_min_duration" {
#   description = "Minimum query duration in ms to be logged as a slow query. 0 to disable."
#   type        = number
#   default     = 500 # ms
# }
# variable "log_connections" {
#   description = "Log connections to the database."
#   type        = bool
#   default     = false # Can be verbose
# }
# variable "log_disconnections" {
#   description = "Log disconnections from thedatabase."
#   type        = bool
#   default     = false # Can be verbose
# }

# Note: Actual database_flags are set in main.tf. This file describes what should be set.

# --- Notification Channel Variables ---
variable "critical_alert_email" {
  description = "Email address for critical alerts."
  type        = string
}

variable "warning_alert_email" {
  description = "Email address for warning alerts."
  type        = string
}

# --- Notification Channels ---
resource "google_monitoring_notification_channel" "email_critical" {
  count        = var.critical_alert_email != "" ? 1 : 0
  project      = var.project_id
  display_name = "Critical Alerts Email"
  type         = "email"
  labels = {
    email_address = var.critical_alert_email
  }
  description = "Email channel for critical alerts."
}

resource "google_monitoring_notification_channel" "email_warning" {
  count        = var.warning_alert_email != "" ? 1 : 0
  project      = var.project_id
  display_name = "Warning Alerts Email"
  type         = "email"
  labels = {
    email_address = var.warning_alert_email
  }
  description = "Email channel for warning alerts."
}

# --- Monitoring Alerts ---

# Alert for high CPU utilization
resource "google_monitoring_alert_policy" "db_high_cpu" {
  project      = var.project_id
  display_name = "${var.instance_name} - High CPU Utilization"
  combiner     = "OR"
  conditions {
    display_name = "Database CPU Utilization > ${var.cpu_alert_threshold_percent}%"
    condition_threshold {
      filter          = "metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\" resource.type=\"cloudsql_database\" resource.labels.database_id=\"${var.project_id}:${var.instance_name}\""
      duration        = "600s" # 10 minutes
      comparison      = "COMPARISON_GT"
      threshold_value = var.cpu_alert_threshold_percent / 100 # Threshold is 0-1
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger {
        count = 1
      }
    }
  }
  notification_channels = var.warning_alert_email != "" ? [google_monitoring_notification_channel.email_warning[0].id] : []
  documentation {
    content   = "The Cloud SQL instance ${var.instance_name} is experiencing high CPU utilization."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "warning"
    "tier"     = "database"
  }
}

# Alert for low available memory
resource "google_monitoring_alert_policy" "db_low_memory" {
  project      = var.project_id
  display_name = "${var.instance_name} - Low Available Memory"
  combiner     = "OR"
  conditions {
    display_name = "Database Available Memory < ${var.memory_alert_threshold_gb}GB"
    condition_threshold {
      filter          = "metric.type=\"cloudsql.googleapis.com/database/memory/quota\" resource.type=\"cloudsql_database\" resource.labels.database_id=\"${var.project_id}:${var.instance_name}\""
      duration        = "600s" # 10 minutes
      comparison      = "COMPARISON_LT"
      threshold_value = var.memory_alert_threshold_gb * 1024 * 1024 * 1024 # Bytes
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger {
        count = 1
      }
    }
  }
  notification_channels = var.warning_alert_email != "" ? [google_monitoring_notification_channel.email_warning[0].id] : []
  documentation {
    content   = "The Cloud SQL instance ${var.instance_name} is running low on available memory."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "warning"
    "tier"     = "database"
  }
}

# Alert for replica lag (if replicas are used)
# This requires a replica instance to be defined.
# variable "replica_lag_alert_threshold_seconds" {
#   description = "Maximum replica lag in seconds before an alert is triggered."
#   type        = number
#   default     = 300 # 5 minutes
# }
# resource "google_monitoring_alert_policy" "db_replica_lag" {
#   count        = var.enable_read_replica ? 1 : 0 # Assuming a var.enable_read_replica
#   project      = var.project_id
#   display_name = "\${var.instance_name} - High Replica Lag"
#   combiner     = "OR"
#   conditions {
#     display_name = "Database Replica Lag > \${var.replica_lag_alert_threshold_seconds}s"
#     condition_threshold {
#       # Ensure this filter correctly targets your replica instance(s)
#       filter     = "metric.type=\"cloudsql.googleapis.com/database/replication/replica_lag\" resource.type=\"cloudsql_database\" resource.labels.database_id=\"\${var.project_id}:\${google_sql_database_instance.replica[0].name}\"" # Example for one replica
#       duration   = "300s" # 5 minutes
#       comparison = "COMPARISON_GT"
#       threshold_value = var.replica_lag_alert_threshold_seconds
#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_MAX"
#       }
#       trigger {
#         count = 1
#       }
#     }
#   }
#   notification_channels = var.critical_alert_email != "" ? [google_monitoring_notification_channel.email_critical[0].id] : []
#   documentation {
#     content = "The Cloud SQL replica for \${var.instance_name} is experiencing high replication lag."
#     mime_type = "text/markdown"
#   }
#   user_labels = {
#     "severity" = "critical"
#     "tier"     = "database"
#   }
# }

# Critical Alert - Database Connectivity Lost
resource "google_monitoring_alert_policy" "db_connectivity_lost" {
  project      = var.project_id
  display_name = "${var.instance_name} - Database Connectivity Lost"
  combiner     = "OR"
  conditions {
    display_name = "No data received from database for > 5 minutes"
    condition_absent {
      filter   = "metric.type=\"cloudsql.googleapis.com/database/disk/read_bytes_count\" resource.type=\"cloudsql_database\" resource.labels.database_id=\"${var.project_id}:${var.instance_name}\""
      duration = "300s" # 5 minutes
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT" # Check if any data point arrived
      }
      trigger {
        count = 1 # Alert if no data point in the alignment period for 5 minutes
      }
    }
  }
  alert_strategy {
    auto_close = "3600s" # Auto-close after 1 hour if condition is no longer met
  }
  notification_channels = var.critical_alert_email != "" ? [google_monitoring_notification_channel.email_critical[0].id] : []
  documentation {
    content   = "The Cloud SQL instance ${var.instance_name} has not reported any disk read activity for over 5 minutes, suggesting a potential connectivity issue or instance outage."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "critical"
    "tier"     = "database"
  }
}

# Placeholder for connection pool utilization alert - This is typically an application-level metric
# or requires custom metrics if monitoring Cloud SQL Proxy connections.
# Cloud SQL itself doesn't directly expose a "connection pool utilization" metric
# in the same way an application-side pool (like HikariCP, PgBouncer) would.
# For now, we can monitor `cloudsql.googleapis.com/database/postgresql/num_backends` as a proxy for active connections.

# variable "max_connections_alert_threshold_percent" {
#   description = "Threshold for active connections as a percentage of max_connections before an alert."
#   type        = number
#   default     = 80
# }

# resource "google_monitoring_alert_policy" "db_high_connections" {
#   project      = var.project_id
#   display_name = "\${var.instance_name} - High Number of Connections"
#   combiner     = "OR"
#   conditions {
#     display_name = "Database Connections > \${var.max_connections_alert_threshold_percent}% of configured max"
#     # This condition requires knowing the max_connections flag value.
#     # It's more complex as it might involve querying the flag value or setting it as a variable.
#     # A simpler approach is to alert on a raw number of connections if a typical max is known.
#     condition_threshold {
#       filter     = "metric.type=\"cloudsql.googleapis.com/database/postgresql/num_backends\" resource.type=\"cloudsql_database\" resource.labels.database_id=\"\${var.project_id}:\${var.instance_name}\""
#       duration   = "300s" # 5 minutes
#       comparison = "COMPARISON_GT"
#       # threshold_value = var.max_connections_limit * (var.max_connections_alert_threshold_percent / 100) # Needs var.max_connections_limit
#       threshold_value = 100 # Example: Alert if more than 100 active connections. Define this as a variable.
#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_MAX"
#       }
#       trigger {
#         count = 1
#       }
#     }
#   }
#   notification_channels = var.warning_alert_email != "" ? [google_monitoring_notification_channel.email_warning[0].id] : []
#   documentation {
#     content = "The Cloud SQL instance \${var.instance_name} has a high number of active connections."
#     mime_type = "text/markdown"
#   }
#   user_labels = {
#     "severity" = "warning"
#     "tier"     = "database"
#   }
# }
