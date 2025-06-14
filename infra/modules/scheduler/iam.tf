// Service Account for the Scheduler Cloud Run service
resource "google_service_account" "cloud_run_sa" {
  count        = var.scheduler_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = substr("cr-sched-${var.service_name}", 0, 30)
  display_name = "SA for ${var.service_name} Cloud Run"
}

locals {
  cloud_run_sa_email = var.scheduler_service_account_email == null ? google_service_account.cloud_run_sa[0].email : var.scheduler_service_account_email
}

// Grant Cloud Run SA access to secrets if used
resource "google_project_iam_member" "run_sa_secret_accessor" {
  count   = length(var.secret_environment_variables) > 0 && (var.scheduler_service_account_email == null) ? 1 : 0
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${local.cloud_run_sa_email}"
}

// Grant Cloud Run SA access to Cloud SQL if VPC connector is used
resource "google_project_iam_member" "run_sa_cloudsql_client" {
  count   = var.vpc_connector_id != null && (var.scheduler_service_account_email == null) ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.cloud_run_sa_email}"
}

// Service Account for the Cloud Scheduler Job to invoke the Cloud Run service
resource "google_service_account" "scheduler_job_sa" {
  count        = var.scheduler_job_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = substr("cs-${var.scheduler_job_name}", 0, 30)
  display_name = "SA for ${var.scheduler_job_name} Job"
}

locals {
  scheduler_job_sa_email = var.scheduler_job_service_account_email == null ? google_service_account.scheduler_job_sa[0].email : var.scheduler_job_service_account_email
}

// Grant the Scheduler Job SA permission to invoke the Scheduler Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "scheduler_job_invoker" {
  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.scheduler_service.name // Refers to the Cloud Run service in main.tf
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.scheduler_job_sa_email}"

  depends_on = [google_cloud_run_v2_service.scheduler_service]
}
