// Service Account for the Collector Cloud Run service
resource "google_service_account" "cloud_run_sa" {
  count        = var.collector_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = substr("cr-coll-${var.service_name}", 0, 30)
  display_name = "SA for ${var.service_name} Cloud Run"
}

locals {
  cloud_run_sa_email = var.collector_service_account_email == null ? google_service_account.cloud_run_sa[0].email : var.collector_service_account_email
}

// Grant Cloud Run SA access to secrets if used
resource "google_project_iam_member" "run_sa_secret_accessor" {
  count   = length(var.secret_environment_variables) > 0 && (var.collector_service_account_email == null) ? 1 : 0
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${local.cloud_run_sa_email}"
}

// Grant Cloud Run SA access to Cloud SQL if VPC connector is used
resource "google_project_iam_member" "run_sa_cloudsql_client" {
  count   = var.vpc_connector_id != null && (var.collector_service_account_email == null) ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.cloud_run_sa_email}"
}

// Service Account for Pub/Sub to use for OIDC token when invoking Cloud Run
// This SA needs roles/run.invoker on the collector Cloud Run service.
// Google creates and manages a default Pub/Sub service account: service-{PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com
// However, for fine-grained permissions with OIDC, it's better to create a dedicated SA for the push subscription.
resource "google_service_account" "pubsub_push_sa" {
  project      = var.project_id
  account_id   = substr("ps-push-${var.service_name}", 0, 30)
  display_name = "SA for Pub/Sub push to ${var.service_name}"
}

locals {
  // This local refers to the SA created above for the push subscription.
  pubsub_push_sa_email = google_service_account.pubsub_push_sa.email
}

// Grant the Pub/Sub Push SA permission to invoke the Collector Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "pubsub_push_invoker" {
  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.collector_service.name // Refers to the Cloud Run service in main.tf
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.pubsub_push_sa_email}"

  depends_on = [
    google_cloud_run_v2_service.collector_service,
    google_service_account.pubsub_push_sa
  ]
}

// The Pub/Sub service itself (Google-managed SA: service-{PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com)
// needs to be able to create tokens for the `pubsub_push_sa_email` to impersonate it for OIDC.
// This is typically "roles/iam.serviceAccountTokenCreator"
// We need the project number for this.
data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "pubsub_sa_token_creator" {
  service_account_id = google_service_account.pubsub_push_sa.name // The SA we created for push
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"

  depends_on = [google_service_account.pubsub_push_sa]
}
