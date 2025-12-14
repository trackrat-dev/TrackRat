# Network Configuration
# Uses default VPC with minimal firewall rules

# Allow health checks from GCP load balancer
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

# Allow SSH for debugging (optional, can be removed in production)
resource "google_compute_firewall" "allow_ssh" {
  name    = "trackrat-${var.environment}-allow-ssh"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["trackrat-${var.environment}"]

  depends_on = [google_project_service.apis]
}
