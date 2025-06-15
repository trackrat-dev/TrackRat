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

# Individual secrets for each configuration value
resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.app_name}-${var.environment}-database-url"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "database"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "njt_username" {
  secret_id = "${var.app_name}-${var.environment}-njt-username"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "api-credentials"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "njt_password" {
  secret_id = "${var.app_name}-${var.environment}-njt-password"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "api-credentials"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "amtrak_api_key" {
  secret_id = "${var.app_name}-${var.environment}-amtrak-api-key"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "api-credentials"
  }

  replication {
    auto {}
  }
}

# Secret versions with initial values
resource "google_secret_manager_secret_version" "database_url_version" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_host != "" && var.database_name != "" && var.database_user != "" && var.database_password != "" ? "postgresql://${var.database_user}:${var.database_password}@${var.database_host}:5432/${var.database_name}" : "postgresql://placeholder"

  lifecycle {
    ignore_changes = []
  }
}

resource "google_secret_manager_secret_version" "njt_username_version" {
  secret      = google_secret_manager_secret.njt_username.id
  secret_data = var.nj_transit_username != "" ? var.nj_transit_username : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "njt_password_version" {
  secret      = google_secret_manager_secret.njt_password.id
  secret_data = var.nj_transit_password != "" ? var.nj_transit_password : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "amtrak_api_key_version" {
  secret      = google_secret_manager_secret.amtrak_api_key.id
  secret_data = var.amtrak_api_key != "" ? var.amtrak_api_key : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Database password is now auto-generated and stored in the database module
