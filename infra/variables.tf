variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-east1-b"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "trackrat"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_service_connection_ip_range" {
  description = "The IP CIDR range to reserve for private service connection (e.g., Cloud SQL, Memorystore). Must be /20 or shorter prefix for sufficient capacity."
  type        = string
  default     = "10.100.0.0/20"
}

# db_password is now auto-generated in the database module

variable "artifact_registry_repository_name" {
  description = "Custom Artifact Registry repository name (optional). If not provided, defaults to {app_name}-{environment}"
  type        = string
  default     = ""
}

# Database connection parameters are now managed by the database module

variable "nj_transit_username" {
  description = "NJ Transit API username"
  type        = string
  sensitive   = true
  default     = ""
}

variable "nj_transit_password" {
  description = "NJ Transit API password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "nj_transit_token" {
  description = "NJ Transit API token (alternative to username/password)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "amtrak_api_key" {
  description = "Amtrak API key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "apns_team_id" {
  description = "Apple Developer Team ID for APNS"
  type        = string
  default     = ""
  sensitive   = true
}

variable "apns_key_id" {
  description = "APNS Auth Key ID"
  type        = string
  default     = ""
  sensitive   = true
}

