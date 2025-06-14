terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# VPC Network
resource "google_compute_network" "vpc" {
  name                    = "${var.app_name}-${var.environment}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "VPC network for ${var.app_name} ${var.environment} environment (CIDR: ${var.vpc_cidr})"
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.app_name}-${var.environment}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  description   = "Subnet for ${var.app_name} ${var.environment} environment"

  # Enable private Google access for serverless resources
  private_ip_google_access = true
}

# Cloud Router for NAT
resource "google_compute_router" "router" {
  name    = "${var.app_name}-${var.environment}-router"
  region  = var.region
  network = google_compute_network.vpc.id

  description = "Router for ${var.app_name} ${var.environment} environment"
}

# Cloud NAT for outbound internet access
resource "google_compute_router_nat" "nat" {
  name   = "${var.app_name}-${var.environment}-nat"
  router = google_compute_router.router.name
  region = var.region

  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Firewall rule to allow health checks
resource "google_compute_firewall" "allow_health_check" {
  name    = "${var.app_name}-${var.environment}-allow-health-check"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["${var.app_name}-${var.environment}"]

  description = "Allow health check traffic for ${var.app_name} ${var.environment}"
}

# Firewall rule to allow internal communication
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.app_name}-${var.environment}-allow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]

  description = "Allow internal communication within VPC for ${var.app_name} ${var.environment}"
}

# Private Service Connection for services like Cloud SQL
resource "google_compute_global_address" "private_service_connection_range" {
  name          = "\${var.app_name}-\${var.environment}-psc-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = tonumber(split("/", var.private_service_connection_ip_range)[1]) # Extracts prefix length
  address       = split("/", var.private_service_connection_ip_range)[0]           # Extracts address part
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "default" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_connection_range.name]
}
