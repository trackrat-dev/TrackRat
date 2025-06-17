output "network_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.vpc.name
}

output "network_id" {
  description = "ID of the VPC network"
  value       = google_compute_network.vpc.id
}

output "subnet_name" {
  description = "Name of the subnet"
  value       = google_compute_subnetwork.subnet.name
}

output "subnet_id" {
  description = "ID of the subnet"
  value       = google_compute_subnetwork.subnet.id
}

output "router_name" {
  description = "Name of the Cloud Router"
  value       = google_compute_router.router.name
}

output "network_self_link" {
  description = "The self-link of the VPC network, for use in Cloud SQL private IP configuration."
  value       = google_compute_network.vpc.self_link
}

output "service_networking_connection" {
  description = "The service networking connection for private services like Cloud SQL"
  value       = google_service_networking_connection.default
}