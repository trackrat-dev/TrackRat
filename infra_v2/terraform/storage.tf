# Storage Configuration
# Artifact Registry for container images and persistent disks for data

# Artifact Registry repository (shared between environments)
resource "google_artifact_registry_repository" "trackrat" {
  location      = var.region
  repository_id = "trackrat"
  description   = "TrackRat container images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}

# Persistent disk for PostgreSQL data and application state
resource "google_compute_disk" "data" {
  name = "trackrat-${var.environment}-data"
  type = "pd-ssd"
  zone = var.zone
  size = var.disk_size_gb

  labels = {
    app         = "trackrat"
    environment = var.environment
  }

  depends_on = [google_project_service.apis]
}

# GCS bucket for docker-compose.yml and deployment artifacts
resource "google_storage_bucket" "deploy" {
  name     = "trackrat-v2-deploy-${var.environment}"
  location = var.region
  project  = var.project_id

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}
