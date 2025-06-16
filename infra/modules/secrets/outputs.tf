# Database URL secret output moved to database module

output "njt_username_secret_name" {
  description = "Name of the NJ Transit username secret"
  value       = google_secret_manager_secret.njt_username.secret_id
}

output "njt_password_secret_name" {
  description = "Name of the NJ Transit password secret"
  value       = google_secret_manager_secret.njt_password.secret_id
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = google_secret_manager_secret.amtrak_api_key.secret_id
}

# Database password outputs moved to database module