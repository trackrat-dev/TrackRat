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

# Database URL secret is now managed by the database module

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

resource "google_secret_manager_secret" "njt_token" {
  secret_id = "${var.app_name}-${var.environment}-njt-token"

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

# Database URL secret version is now managed by the database module

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

resource "google_secret_manager_secret_version" "njt_token_version" {
  secret      = google_secret_manager_secret.njt_token.id
  secret_data = var.nj_transit_token != "" ? var.nj_transit_token : "placeholder"

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

# APNS secrets
resource "google_secret_manager_secret" "apns_team_id" {
  secret_id = "${var.app_name}-${var.environment}-apns-team-id"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "apns-credentials"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "apns_key_id" {
  secret_id = "${var.app_name}-${var.environment}-apns-key-id"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "apns-credentials"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "apns_auth_key" {
  secret_id = "${var.app_name}-${var.environment}-apns-auth-key"

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "apns-credentials"
  }

  replication {
    auto {}
  }
}


resource "google_secret_manager_secret_version" "apns_team_id_version" {
  secret      = google_secret_manager_secret.apns_team_id.id
  secret_data = var.apns_team_id != "" ? var.apns_team_id : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "apns_key_id_version" {
  secret      = google_secret_manager_secret.apns_key_id.id
  secret_data = var.apns_key_id != "" ? var.apns_key_id : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "apns_auth_key_version" {
  secret      = google_secret_manager_secret.apns_auth_key.id
  secret_data = var.apns_auth_key != "" ? var.apns_auth_key : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Database password is now auto-generated and stored in the database module
