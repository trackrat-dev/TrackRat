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