variable "name" {
  description = "Name of the VPC Access Connector"
  type        = string
}

variable "region" {
  description = "GCP region for the VPC Access Connector"
  type        = string
}

variable "network_name" {
  description = "Name of the VPC network"
  type        = string
}

variable "ip_cidr_range" {
  description = "IP CIDR range for the VPC Access Connector (must be /28)"
  type        = string
  validation {
    condition     = can(regex(".*\\/28$", var.ip_cidr_range))
    error_message = "IP CIDR range must be a /28 subnet."
  }
}