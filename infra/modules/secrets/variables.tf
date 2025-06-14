variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "db_password_plaintext" {
  description = "The plaintext database password to be stored in Secret Manager. This should be provided securely."
  type        = string
  sensitive   = true
  default     = null # Ensure it's provided if resources are created
}

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