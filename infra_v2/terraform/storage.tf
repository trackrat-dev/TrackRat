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
  type = "pd-balanced"
  zone = var.zone
  size = var.disk_size_gb

  labels = {
    app         = "trackrat"
    environment = var.environment
  }

  # Ignore snapshot attribute - disk may have been created from snapshot
  # but we don't want Terraform to recreate it
  lifecycle {
    ignore_changes = [snapshot]
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

  # Scoped to ARCHIVED (noncurrent) generations ONLY.
  #
  # Without with_state this rule deletes the LIVE object too, and this bucket is
  # the MIG's bootstrap source: the startup script downloads docker-compose.yml
  # and docker-compose.tunnel.yml from here on every boot (compute.tf). Going 30
  # days without a deploy therefore aged out the live bootstrap artifacts while
  # the running VM kept serving from its data-disk copy — so nothing broke until
  # the next instance recreate, which then could not boot at all. That is the
  # 33-minute production outage on 2026-09-20 (issue #1823).
  #
  # Versioning is enabled above, so garbage-collecting old generations after 30
  # days keeps the original intent; the live object is now never removed.
  lifecycle_rule {
    condition {
      age        = 30
      with_state = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}
