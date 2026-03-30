# Secrets and IAM Configuration

# Reference existing secrets (must be created manually before terraform apply)
# Required secrets:
#   - trackrat-db-password: PostgreSQL password
#   - trackrat-njt-api-token: NJ Transit API token
#   - trackrat-apns-team-id: APNS Team ID
#   - trackrat-apns-key-id: APNS Key ID
#   - trackrat-apns-bundle-id: APNS Bundle ID
#   - trackrat-apns-auth-key: APNS Auth Key (P8 content)
#   - trackrat-wmata-api-key: WMATA developer API key
#   - trackrat-metra-api-token: Metra GTFS-RT API token

data "google_secret_manager_secret" "db_password" {
  secret_id  = "trackrat-db-password"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "njt_api_token" {
  secret_id  = "trackrat-njt-api-token"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "apns_team_id" {
  secret_id  = "trackrat-apns-team-id"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "apns_key_id" {
  secret_id  = "trackrat-apns-key-id"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "apns_bundle_id" {
  secret_id  = "trackrat-apns-bundle-id"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "apns_auth_key" {
  secret_id  = "trackrat-apns-auth-key"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "wmata_api_key" {
  secret_id  = "trackrat-wmata-api-key"
  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret" "metra_api_token" {
  secret_id  = "trackrat-metra-api-token"
  depends_on = [google_project_service.apis]
}

# Service account for TrackRat VMs
resource "google_service_account" "trackrat" {
  account_id   = "trackrat-${var.environment}"
  display_name = "TrackRat ${title(var.environment)} Service Account"
  depends_on   = [google_project_service.apis]
}

# Secret access permissions
resource "google_secret_manager_secret_iam_member" "db_password" {
  secret_id = data.google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "njt_api_token" {
  secret_id = data.google_secret_manager_secret.njt_api_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "wmata_api_key" {
  secret_id = data.google_secret_manager_secret.wmata_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "metra_api_token" {
  secret_id = data.google_secret_manager_secret.metra_api_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "apns_team_id" {
  secret_id = data.google_secret_manager_secret.apns_team_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "apns_key_id" {
  secret_id = data.google_secret_manager_secret.apns_key_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "apns_bundle_id" {
  secret_id = data.google_secret_manager_secret.apns_bundle_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

resource "google_secret_manager_secret_iam_member" "apns_auth_key" {
  secret_id = data.google_secret_manager_secret.apns_auth_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.trackrat.email}"
}

# Artifact Registry read access
resource "google_artifact_registry_repository_iam_member" "trackrat_reader" {
  location   = google_artifact_registry_repository.trackrat.location
  repository = google_artifact_registry_repository.trackrat.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.trackrat.email}"
}

# Logging permissions
resource "google_project_iam_member" "trackrat_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.trackrat.email}"
}

# Custom role for disk attachment (minimal permissions)
resource "google_project_iam_custom_role" "disk_attacher" {
  role_id     = "trackratDiskAttacher${title(var.environment)}"
  title       = "TrackRat Disk Attacher (${var.environment})"
  description = "Minimal permissions to attach/detach persistent disks"
  permissions = [
    "compute.instances.attachDisk",
    "compute.instances.detachDisk",
    "compute.instances.get",
    "compute.disks.use",
    "compute.zoneOperations.get",
  ]
}

resource "google_project_iam_member" "trackrat_disk_attacher" {
  project = var.project_id
  role    = google_project_iam_custom_role.disk_attacher.id
  member  = "serviceAccount:${google_service_account.trackrat.email}"
}

# Self-user permission (required for attach-disk from within VM)
resource "google_service_account_iam_member" "trackrat_self_user" {
  service_account_id = google_service_account.trackrat.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.trackrat.email}"
}

# GCS bucket access for deployment artifacts
resource "google_storage_bucket_iam_member" "trackrat_deploy_reader" {
  bucket = google_storage_bucket.deploy.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.trackrat.email}"
}

# =============================================================================
# Cloud Build Service Account Permissions
# =============================================================================

# Cloud Build triggers use trackrat-staging SA for all Terraform operations
# (both staging and production workspaces). This SA needs monitoring.admin
# to manage uptime checks and alert policies in the production workspace.
resource "google_project_iam_member" "cloudbuild_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.admin"
  member  = "serviceAccount:trackrat-staging@trackrat-v2.iam.gserviceaccount.com"
}

# Cloud Build also needs logging.configWriter to create log-based metrics
# (google_logging_metric resources in metrics.tf).
resource "google_project_iam_member" "cloudbuild_logging" {
  project = var.project_id
  role    = "roles/logging.configWriter"
  member  = "serviceAccount:trackrat-staging@trackrat-v2.iam.gserviceaccount.com"
}
