variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

# db_password is now auto-generated in the database module

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

variable "amtrak_api_key" {
  description = "Amtrak API key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

# Database connection parameters
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