resource "google_vpc_access_connector" "default" {
  name          = var.name
  region        = var.region
  network       = var.network_name
  ip_cidr_range = var.ip_cidr_range

  # Use e2-micro for cost efficiency
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3
  # Throughput settings (min must be less than max)
  min_throughput = 200
  max_throughput = 300
}
