# Dev environment configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "trackrat-dev-terraform-state"
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
  environment                         = "dev"
  app_name                            = "trackrat"
  vpc_cidr                            = "10.1.0.0/16"
  subnet_cidr                         = "10.1.1.0/24"
  private_service_connection_ip_range = "10.1.16.0/20"
  # db_password is now auto-generated in the database module
  artifact_registry_repository_name = "trackcast-inference-dev"

  # Database connection parameters are now managed by the database module
}

module "database" {
  source = "../../modules/database"

  project_id                    = var.project_id
  region                        = var.region
  instance_name                 = "${var.app_name}-${var.environment}-sql" # Example instance name
  instance_tier                 = "db-f1-micro"
  network_self_link             = module.infrastructure.network_self_link # From VPC module output
  service_networking_connection = module.infrastructure.service_networking_connection

  # database_user_password is now auto-generated in the database module

  # Alert notification emails
  critical_alert_email = var.critical_alert_email
  warning_alert_email  = var.warning_alert_email

  # Adjust other variables as needed for the dev environment
  maintenance_window_day  = 7     # Sunday
  maintenance_window_hour = 2     # 2 AM UTC for dev
  deletion_protection     = false # Dev can have deletion protection off
}

module "vpc_connector" {
  source = "../../modules/vpc-connector"

  name          = "${var.app_name}-${var.environment}-vpc"
  region        = var.region
  network_name  = module.infrastructure.vpc_network_name
  ip_cidr_range = "10.1.2.0/28" # Dedicated /28 range outside the subnet to avoid conflict
}

module "trackrat_api_service" {
  source = "../../modules/cloud-run"

  project_id      = var.project_id
  location        = var.region         # Assuming 'region' is defined in dev/variables.tf
  service_name    = "trackrat-api-dev" # Append env for clarity
  container_image = var.api_image_url  # To be defined in variables.tf
  container_port  = 8000               # Assuming the API runs on port 8000

  cpu_limit               = "1"   # Reduced since no longer handling scheduler operations
  memory_limit            = "1Gi" # Reduced since no longer handling scheduler operations  
  concurrency             = 100
  min_instances           = 0  # Scale to 0 since using Cloud Run Jobs for operations
  max_instances           = 2  # Increased for user traffic handling
  request_timeout_seconds = 60 # Reduced to normal API timeout

  # Assuming /health is the correct endpoint for trackrat-api
  startup_probe_path                  = "/health"
  startup_probe_initial_delay_seconds = 30 # Give app time to start
  startup_probe_timeout_seconds       = 10 # Increase timeout per probe
  startup_probe_period_seconds        = 15 # Check every 15 seconds
  startup_probe_failure_threshold     = 40 # 40 attempts = 10 minutes total
  liveness_probe_path                 = "/health"
  liveness_probe_period_seconds       = 30

  vpc_connector_id       = module.vpc_connector.id # Reference the VPC connector we created
  enable_cloudsql_access = true                    # Enable Cloud SQL access permissions

  # Environment variables (non-sensitive)
  environment_variables = {
    APP_ENV                     = "development"
    TRACKCAST_ENV               = "dev"
    MODEL_PATH                  = "/app/models"
    TRACKCAST_SCHEDULER_MODE    = "cloud_native"      # Enable cloud-native mode to disable internal scheduler
    GOOGLE_CLOUD_PROJECT        = var.project_id      # Automatically enable GCP Cloud Trace and Metrics
    OTEL_SAMPLE_RATE            = "1"                 # 100% sampling for development debugging
    OTEL_SERVICE_NAME           = "trackcast-api-dev" # Environment-specific service name
    GCP_METRICS_EXPORT_INTERVAL = "60"                # Export metrics to GCP every 60 seconds
  }

  # Secret environment variables (sensitive data from Secret Manager)
  secret_environment_variables = {
    DATABASE_URL = "${module.database.database_url_secret_name}:latest"
    NJT_USERNAME = "${module.infrastructure.njt_username_secret_name}:latest"
    NJT_PASSWORD = "${module.infrastructure.njt_password_secret_name}:latest"
    NJT_TOKEN    = "${module.infrastructure.njt_token_secret_name}:latest"
  }

  # If a specific service account is already created for the API for this env:
  # service_account_email = "existing-sa@${var.project_id}.iam.gserviceaccount.com"

  # Custom domain configuration
  enable_custom_domain = var.enable_custom_domain
  custom_domain_name   = var.custom_domain_name

  labels = {
    service = "trackrat-api"
    env     = "dev"
  }

  depends_on = [
    module.database,      # Database must be created before Cloud Run
    module.vpc_connector, # VPC connector needed for database connectivity
    module.infrastructure # Infrastructure (including secrets) must be ready
  ]
}

# Service account for Cloud Scheduler jobs to invoke Cloud Run Jobs
resource "google_service_account" "scheduler_sa" {
  project      = var.project_id
  account_id   = "trackrat-scheduler-dev"
  display_name = "TrackRat Scheduler Service Account (Dev)"
  description  = "Service account for Cloud Scheduler jobs to invoke Cloud Run Jobs"
}

# Cloud Run Jobs for scheduled operations
module "scheduled_operations" {
  source = "../../modules/cloud-run-jobs"

  project_id            = var.project_id
  location              = var.region
  job_name_prefix       = "trackrat-ops-dev"
  container_image       = var.api_image_url
  service_account_email = google_service_account.scheduler_sa.email
  vpc_connector_id      = module.vpc_connector.id

  # Global environment variables for all jobs
  environment_variables = {
    APP_ENV                     = "development"
    TRACKCAST_ENV               = "dev"
    MODEL_PATH                  = "/app/models"
    TRACKCAST_SCHEDULER_MODE    = "cloud_native"
    GOOGLE_CLOUD_PROJECT        = var.project_id      # Automatically enable GCP Cloud Trace and Metrics
    OTEL_SAMPLE_RATE            = "1"                 # 100% sampling for development debugging
    OTEL_SERVICE_NAME           = "trackcast-ops-dev" # Environment-specific service name for jobs
    GCP_METRICS_EXPORT_INTERVAL = "60"                # Export metrics to GCP every 60 seconds
  }

  # Secret environment variables from Secret Manager
  secret_environment_variables = {
    DATABASE_URL = "${module.database.database_url_secret_name}:latest"
    NJT_USERNAME = "${module.infrastructure.njt_username_secret_name}:latest"
    NJT_PASSWORD = "${module.infrastructure.njt_password_secret_name}:latest"
    NJT_TOKEN    = "${module.infrastructure.njt_token_secret_name}:latest"
  }

  # Job configurations
  jobs = {
    pipeline = {
      command      = ["trackcast", "run-pipeline", "--regenerate"]
      cpu_limit    = "1"
      memory_limit = "1Gi"
      max_retries  = 1
      task_timeout = "300s"
      environment_variables = {
        JOB_TYPE = "pipeline"
      }
    }
  }

  labels = {
    environment = "dev"
    component   = "scheduler"
  }

  depends_on = [
    module.database,
    module.vpc_connector,
    module.infrastructure
  ]
}

# Grant Cloud Trace Agent role to the scheduler service account for tracing
resource "google_project_iam_member" "scheduler_cloud_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# Grant Monitoring Metric Writer role to the scheduler service account for GCP metrics export
resource "google_project_iam_member" "scheduler_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# IAM permissions for jobs are handled at the job level in the cloud-run-jobs module


# Cloud Scheduler jobs targeting Cloud Run Jobs
resource "google_cloud_scheduler_job" "operations" {
  for_each = {
    # Consolidated pipeline scheduler - runs every 10m
    pipeline = {
      schedule    = "*/10 * * * *" # Every 10m
      description = "Complete data pipeline: collection -> features -> predictions every 10m"
      job_name    = "pipeline"
    }
  }

  project          = var.project_id
  region           = var.region
  name             = "trackrat-ops-dev-${each.value.job_name}-scheduler-trigger"
  description      = each.value.description
  schedule         = each.value.schedule
  time_zone        = "America/New_York"
  attempt_deadline = "180s"

  retry_config {
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/trackrat-ops-dev-${each.value.job_name}:run"
    http_method = "POST"

    headers = {
      "User-Agent" = "Google-Cloud-Scheduler"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler_sa.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    module.scheduled_operations,
    google_service_account.scheduler_sa
  ]
}
