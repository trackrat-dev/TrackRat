# Database URL secret output moved to database module

output "njt_username_secret_name" {
  description = "Name of the NJ Transit username secret"
  value       = google_secret_manager_secret.njt_username.secret_id
}

output "njt_password_secret_name" {
  description = "Name of the NJ Transit password secret"
  value       = google_secret_manager_secret.njt_password.secret_id
}

output "njt_token_secret_name" {
  description = "Name of the NJ Transit token secret"
  value       = google_secret_manager_secret.njt_token.secret_id
}

output "amtrak_api_key_secret_name" {
  description = "Name of the Amtrak API key secret"
  value       = google_secret_manager_secret.amtrak_api_key.secret_id
}

output "apns_team_id_secret_name" {
  description = "Name of the APNS Team ID secret"
  value       = google_secret_manager_secret.apns_team_id.secret_id
}

output "apns_key_id_secret_name" {
  description = "Name of the APNS Key ID secret"
  value       = google_secret_manager_secret.apns_key_id.secret_id
}

output "apns_auth_key_secret_name" {
  description = "Name of the APNS Auth Key secret"
  value       = google_secret_manager_secret.apns_auth_key.secret_id
}

# Database password outputs moved to database module