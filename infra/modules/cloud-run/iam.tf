resource "google_service_account" "default" {
  count        = var.service_account_email == null ? 1 : 0 # Create only if no existing SA is provided
  project      = var.project_id
  account_id   = substr("cr-${var.service_name}", 0, 30) # Max 30 chars for account_id
  display_name = "Service Account for ${var.service_name} Cloud Run"
}

locals {
  effective_service_account_email = var.service_account_email == null ? google_service_account.default[0].email : var.service_account_email
}

# Grant the service account permission to pull images from Artifact Registry (if needed)
# This is a common requirement. Add other roles as necessary.
resource "google_project_iam_member" "artifact_registry_reader" {
  count   = var.service_account_email == null ? 1 : 0 # Manage only if SA is created by this module
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# Allow Cloud Run to be invoked (e.g., by public users, or specific services)
# By default, new Cloud Run services are private. Add invoker role for public access if needed.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# If using secrets, the service account needs access to Secret Manager
resource "google_project_iam_member" "secret_accessor" {
  count   = length(var.secret_environment_variables) > 0 ? 1 : 0 # Only if secrets are used
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# If connecting to Cloud SQL via private IP using the Cloud SQL Auth Proxy,
# the service account needs roles/cloudsql.client
resource "google_project_iam_member" "cloudsql_client" {
  count   = var.enable_cloudsql_access ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# Grant Cloud Trace Agent role for OpenTelemetry tracing
resource "google_project_iam_member" "cloud_trace_agent" {
  count   = var.service_account_email == null ? 1 : 0 # Only if SA is created by this module
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# Grant Monitoring Metric Writer role for GCP metrics export
resource "google_project_iam_member" "monitoring_metric_writer" {
  count   = var.service_account_email == null ? 1 : 0 # Only if SA is created by this module
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# Grant Storage Object Admin role for backup bucket access
resource "google_project_iam_member" "storage_object_admin" {
  count   = var.enable_backup_access ? 1 : 0 # Only if backup is enabled
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${local.effective_service_account_email}"
}

# Add other necessary IAM bindings here, for example, Pub/Sub subscriber if triggered by Pub/Sub, etc.
