terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
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

  # Initial placeholder - replace with actual secrets
  secret_data = jsonencode({
    "database_url"       = "postgresql://placeholder"
    "nj_transit_api_key" = "placeholder"
    "amtrak_api_key"     = "placeholder"
  })

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "db_password" {
  # Check if db_password_plaintext is provided before creating
  count = var.db_password_plaintext != null ? 1 : 0

  secret_id = "trackrat-db-password" # As specified in the issue
  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "database-credentials"
  }
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password_version" {
  # Check if db_password_plaintext is provided before creating
  count = var.db_password_plaintext != null ? 1 : 0

  secret      = google_secret_manager_secret.db_password[0].id
  secret_data = var.db_password_plaintext
}
