terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0"
    }
  }
}

resource "google_vpc_access_connector" "default" {
  name          = var.name
  region        = var.region
  network       = var.network_name
  ip_cidr_range = var.ip_cidr_range

  # Use e2-micro for cost efficiency
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3
}
