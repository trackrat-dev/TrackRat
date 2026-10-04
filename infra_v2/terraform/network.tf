# Network Configuration
# Uses default VPC with minimal firewall rules

# Allow Google health-check probes to reach the API on port 8000.
# There is no load balancer any more (issue #1764), but the MIG's
# auto_healing_policies (compute.tf) probe from these same ranges. Deleting this
# rule breaks auto-healing silently: nothing fails until an instance wedges and
# is not replaced.
resource "google_compute_firewall" "allow_health_checks" {
  name    = "trackrat-${var.environment}-allow-health-checks"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  # GCP health check IP ranges
  source_ranges = [
    "130.211.0.0/22",
    "35.191.0.0/16",
  ]

  target_tags = ["trackrat-${var.environment}"]

  depends_on = [google_project_service.apis]
}

# Allow SSH via IAP tunnel only (use: gcloud compute ssh INSTANCE --tunnel-through-iap)
resource "google_compute_firewall" "allow_ssh" {
  name    = "trackrat-${var.environment}-allow-ssh"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP tunnel IP range only - no direct SSH from internet
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["trackrat-${var.environment}"]

  depends_on = [google_project_service.apis]
}
