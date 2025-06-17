variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR block for subnet"
  type        = string
}

variable "private_service_connection_ip_range" {
  description = "The IP CIDR range to reserve for private service connection (e.g., Cloud SQL, Memorystore). Must be /20 or shorter prefix for sufficient capacity."
  type        = string
  default     = "10.100.0.0/20" # Larger range (4096 IPs) for Google managed services
}