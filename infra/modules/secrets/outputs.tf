output "secret_name" {
  description = "Name of the Secret Manager secret"
  value       = google_secret_manager_secret.app_secrets.secret_id
}

output "secret_id" {
  description = "ID of the Secret Manager secret"
  value       = google_secret_manager_secret.app_secrets.id
}