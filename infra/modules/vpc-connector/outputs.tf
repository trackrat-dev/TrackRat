output "id" {
  description = "Self-link of the VPC Access Connector"
  value       = google_vpc_access_connector.default.id
}

output "name" {
  description = "Name of the VPC Access Connector"
  value       = google_vpc_access_connector.default.name
}

output "state" {
  description = "State of the VPC Access Connector"
  value       = google_vpc_access_connector.default.state
}