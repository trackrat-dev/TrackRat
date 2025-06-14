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
  value       = google_secret_manager_secret.db_password.secret_id
  sensitive   = true
}

output "db_password_secret_version_name" {
  description = "The resource name of the latest version of the database password secret."
  value       = google_secret_manager_secret_version.db_password_version.name
  sensitive   = true
}

output "db_password_secret_name" {
  description = "The full resource name of the database password secret."
  value       = google_secret_manager_secret.db_password.name
  sensitive   = true
}