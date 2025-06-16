output "instance_connection_name" {
  description = "The connection name of the Cloud SQL instance, used by Cloud SQL Proxy and connectors."
  value       = google_sql_database_instance.default.connection_name
}

output "instance_name" {
  description = "The name of the Cloud SQL instance."
  value       = google_sql_database_instance.default.name
}

output "instance_self_link" {
  description = "The self-link of the Cloud SQL instance."
  value       = google_sql_database_instance.default.self_link
}

output "private_ip_address" {
  description = "The private IP address of the Cloud SQL instance."
  # The IP address is available in the ip_address block, specifically the first entry.
  # Ensure that the instance is configured for private IP before accessing this.
  value = try(google_sql_database_instance.default.ip_address[0].ip_address, null) # Access first IP, type PRIVATE
  # Note: This assumes the first IP address listed is the private one.
  # For more robustness, you might iterate or filter if multiple IP types could exist,
  # but for "private IP only", this should be safe.
}

output "database_name" {
  description = "The name of the database created."
  value       = google_sql_database.default.name
}

output "database_user_name" {
  description = "The name of the default database user created."
  value       = google_sql_user.default.name
}

output "db_password_secret_id" {
  description = "The ID of the Secret Manager secret holding the DB password."
  value       = google_secret_manager_secret.database_password.secret_id
}

output "db_password_secret_version_id" {
  description = "The ID of the Secret Manager secret version holding the DB password."
  value       = google_secret_manager_secret_version.database_password_version.id
}

output "instance_service_account_email" {
  description = "The email address of the service account associated with this Cloud SQL instance."
  value       = google_sql_database_instance.default.service_account_email_address
}

output "database_password" {
  description = "The database user password (sensitive)"
  value       = random_password.database_user_password.result
  sensitive   = true
}

output "database_url_secret_name" {
  description = "Name of the database URL secret"
  value       = google_secret_manager_secret.database_url.secret_id
}
