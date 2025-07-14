# Staging environment configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "trackrat-staging-terraform-state"
    prefix = "terraform/state"
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Use the main infrastructure module
module "infrastructure" {
  source = "../../"

  project_id                          = var.project_id
  region                              = var.region
  zone                                = var.zone
  environment                         = "staging"
  app_name                            = "trackrat"
  vpc_cidr                            = "10.2.0.0/16"
  subnet_cidr                         = "10.2.1.0/24"
  private_service_connection_ip_range = "10.2.16.0/20"
  artifact_registry_repository_name   = "trackcast-inference-staging"
}



module "trackrat_api_service" {
  source = "../../modules/cloud-run"

  project_id      = var.project_id
  location        = var.region
  service_name    = "trackrat-api-staging"
  container_image = var.api_image_url
  container_port  = 8000

  cpu_limit               = "1"
  memory_limit            = "512Mi"
  concurrency             = 100
  min_instances           = 0 # Scale to 0 for cost efficiency
  max_instances           = 1
  request_timeout_seconds = 60

  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id       = null
  enable_cloudsql_access = false
  enable_backup_access   = true

  # Environment variables (non-sensitive)
  environment_variables = {
    APP_ENV                      = "staging"
    TRACKCAST_ENV                = "staging"
    TRACKRAT_ENVIRONMENT         = "production"                                       # Use production logging format (JSON, no ANSI)
    APNS_ENVIRONMENT             = "prod"                                             # Use production APNS for TestFlight/production-signed iOS apps
    APNS_BUNDLE_ID               = "net.trackrat.TrackRat"                            # Main app bundle ID
    APNS_LIVE_ACTIVITY_BUNDLE_ID = "net.trackrat.TrackRat.TrainLiveActivityExtension" # Live Activity extension bundle ID
    MODEL_PATH                   = "/app/models"
    TRACKCAST_SCHEDULER_MODE     = "cloud_native"
    GOOGLE_CLOUD_PROJECT         = var.project_id          # Automatically enable GCP Cloud Trace and Metrics
    OTEL_SAMPLE_RATE             = "0.2"                   # Higher sampling for staging environment testing
    OTEL_SERVICE_NAME            = "trackcast-api-staging" # Environment-specific service name
    GCP_METRICS_EXPORT_INTERVAL  = "60"                    # Export metrics to GCP every 60 seconds
    GCS_BACKUP_BUCKET            = module.infrastructure.db_backup_bucket_name
  }

  # Secret environment variables (sensitive data from Secret Manager)
  secret_environment_variables = {
    TRACKRAT_NJT_API_TOKEN = "${module.infrastructure.njt_token_secret_name}:latest"
    APNS_TEAM_ID           = "${module.infrastructure.apns_team_id_secret_name}:latest"
    APNS_KEY_ID            = "${module.infrastructure.apns_key_id_secret_name}:latest"
    # APNS_AUTH_KEY removed - now loaded from file path in container
  }

  # Custom domain configuration
  enable_custom_domain = var.enable_custom_domain
  custom_domain_name   = var.custom_domain_name

  labels = {
    service = "trackrat-api"
    env     = "staging"
  }

  depends_on = [
    module.infrastructure
  ]
}





