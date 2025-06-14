terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
}

# Secret Manager secret for application configuration
resource "google_secret_manager_secret" "app_secrets" {
  secret_id = "${var.app_name}-${var.environment}-secrets"

  labels = {
    app         = var.app_name
    environment = var.environment
  }

  replication {
    auto {}
  }
}

# Example secret version (will be updated via CI/CD or manually)
resource "google_secret_manager_secret_version" "app_secrets_version" {
  secret = google_secret_manager_secret.app_secrets.id

  # Populate with actual secrets if provided, otherwise use placeholders
  secret_data = jsonencode({
    "database_url"        = "postgresql://placeholder"
    "nj_transit_username" = var.nj_transit_username != "" ? var.nj_transit_username : "placeholder"
    "nj_transit_password" = var.nj_transit_password != "" ? var.nj_transit_password : "placeholder"
    "amtrak_api_key"      = var.amtrak_api_key != "" ? var.amtrak_api_key : "placeholder"
  })

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Generate a random password for the database if none provided
resource "random_password" "db_password" {
  count   = var.db_password_plaintext == null || var.db_password_plaintext == "" ? 1 : 0
  length  = 32
  special = true
}

# Always create the database password secret
resource "google_secret_manager_secret" "db_password" {
  secret_id = "trackrat-db-password"
  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "database-credentials"
  }
  replication {
    auto {}
  }
}

# Use provided password or generated one
resource "google_secret_manager_secret_version" "db_password_version" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password_plaintext != null && var.db_password_plaintext != "" ? var.db_password_plaintext : random_password.db_password[0].result
}
