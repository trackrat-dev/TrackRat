terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

resource "google_sql_database_instance" "default" {
  project          = var.project_id
  region           = var.region
  database_version = var.database_version
  name             = var.instance_name
  settings {
    tier = var.instance_tier

    ip_configuration {
      ipv4_enabled    = false # Disable public IP
      private_network = var.network_self_link
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled = true
      # binary_log_enabled is MySQL-only, PostgreSQL uses WAL automatically
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
      point_in_time_recovery_enabled = true
      start_time                     = var.backup_window_start_time != null ? var.backup_window_start_time : null
    }

    maintenance_window {
      day          = var.maintenance_window_day  # 1-7 (Monday-Sunday)
      hour         = var.maintenance_window_hour # 0-23
      update_track = "stable"                    # Or "canary"
    }

    database_flags {
      name  = "log_min_duration_statement"              # For PostgreSQL
      value = tostring(var.slow_query_log_min_duration) # In milliseconds, 0 to disable
    }
    database_flags {
      name  = "log_connections"
      value = var.log_connections ? "on" : "off"
    }
    database_flags {
      name  = "log_disconnections"
      value = var.log_disconnections ? "on" : "off"
    }
    # Add other flags as needed, e.g. for connection limits:
    database_flags {
      name  = "max_connections"
      value = tostring(var.max_connections_limit)
    }
  }

  # Deletion protection can be enabled in production
  deletion_protection = var.deletion_protection
}

# Create a database within the instance
resource "google_sql_database" "default" {
  project   = var.project_id
  instance  = google_sql_database_instance.default.name
  name      = var.database_name
  charset   = "UTF8"
  collation = "en_US.UTF8"
}

# Generate random password for database user
resource "random_password" "database_user_password" {
  length  = 32
  special = true
  upper   = true
  lower   = true
  numeric = true
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "database_password" {
  project   = var.project_id
  secret_id = "${var.instance_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_password_version" {
  secret      = google_secret_manager_secret.database_password.id
  secret_data = random_password.database_user_password.result
}

# Create a user for the database
resource "google_sql_user" "default" {
  project  = var.project_id
  instance = google_sql_database_instance.default.name
  name     = var.database_user_name
  password = random_password.database_user_password.result
  # host can be restricted if needed, e.g. for specific IP ranges
  # host = "%"
}
