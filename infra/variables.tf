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

# db_password is now auto-generated in the database module

variable "artifact_registry_repository_name" {
  description = "Custom Artifact Registry repository name (optional). If not provided, defaults to {app_name}-{environment}"
  type        = string
  default     = ""
}

# Database connection parameters for secrets module
variable "database_host" {
  description = "Database host/IP address"
  type        = string
  default     = ""
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = ""
}

variable "database_user" {
  description = "Database user name"
  type        = string
  default     = ""
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
  default     = ""
}