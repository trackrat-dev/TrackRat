output "secret_name" {
  description = "Name of the Secret Manager secret"
  value       = google_secret_manager_secret.app_secrets.secret_id
}

output "secret_id" {
  description = "ID of the Secret Manager secret"
  value       = google_secret_manager_secret.app_secrets.id
}

output "db_password_secret_id" {
  description = "The secret_id of the database password secret in Secret Manager."
  value       = var.db_password_plaintext != null ? google_secret_manager_secret.db_password[0].secret_id : null
  sensitive   = true
}

output "db_password_secret_version_name" {
  description = "The resource name of the latest version of the database password secret."
  value       = var.db_password_plaintext != null ? google_secret_manager_secret_version.db_password_version[0].name : null
  sensitive   = true
}

output "db_password_secret_name" {
  description = "The full resource name of the database password secret."
  value       = var.db_password_plaintext != null ? google_secret_manager_secret.db_password[0].name : null
  sensitive   = true
}