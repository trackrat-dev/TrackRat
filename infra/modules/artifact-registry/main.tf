terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.repository_name != "" ? var.repository_name : "${var.app_name}-${var.environment}"
  description   = "Docker repository for ${var.app_name} ${var.environment} environment"
  format        = "DOCKER"

  labels = {
    app         = var.app_name
    environment = var.environment
  }

  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old-versions"
    action = "DELETE"

    condition {
      older_than = "2592000s" # 30 days
    }
  }

  lifecycle {
    ignore_changes = [
      # Ignore changes if repository exists
      location,
      repository_id,
      format
    ]
  }
}
