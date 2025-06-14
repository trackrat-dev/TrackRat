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
