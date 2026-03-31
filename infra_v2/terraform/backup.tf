# Backup Configuration
# Daily snapshots of persistent disk

resource "google_compute_resource_policy" "snapshots" {
  name   = "trackrat-${var.environment}-snapshots"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "03:00" # 3 AM UTC
      }
    }

    retention_policy {
      max_retention_days    = var.snapshot_retention_days
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }

    snapshot_properties {
      labels = {
        app         = "trackrat"
        environment = var.environment
      }
      storage_locations = [var.region]
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_compute_disk_resource_policy_attachment" "snapshots" {
  name = google_compute_resource_policy.snapshots.name
  disk = google_compute_disk.data.name
  zone = var.zone

  depends_on = [
    google_compute_resource_policy.snapshots,
    google_compute_disk.data,
  ]
}
