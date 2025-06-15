terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
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
    "DATABASE_URL"   = var.database_host != "" && var.database_name != "" && var.database_user != "" && var.database_password != "" ? "postgresql://${var.database_user}:${var.database_password}@${var.database_host}:5432/${var.database_name}" : "postgresql://placeholder"
    "NJT_USERNAME"   = var.nj_transit_username != "" ? var.nj_transit_username : "placeholder"
    "NJT_PASSWORD"   = var.nj_transit_password != "" ? var.nj_transit_password : "placeholder"
    "AMTRAK_API_KEY" = var.amtrak_api_key != "" ? var.amtrak_api_key : "placeholder"
  })

  lifecycle {
    # Only ignore changes to API credentials, but allow database_url updates
    ignore_changes = []
  }
}

# Database password is now auto-generated and stored in the database module
