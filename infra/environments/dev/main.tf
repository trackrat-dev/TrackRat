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

  project_id  = var.project_id
  region      = var.region
  zone        = var.zone
  environment = "dev"
  app_name    = "trackrat"
  vpc_cidr    = "10.1.0.0/16"
  subnet_cidr = "10.1.1.0/24"
  # db_password is now auto-generated in the database module
  artifact_registry_repository_name = "trackcast-inference-dev"

  # Database connection parameters for secrets module
  database_host     = module.database.private_ip_address
  database_name     = module.database.database_name
  database_user     = module.database.database_user_name
  database_password = module.database.database_password
}

module "database" {
  source = "../../modules/database"

  project_id        = var.project_id
  region            = var.region
  instance_name     = "${var.app_name}-${var.environment}-sql" # Example instance name
  instance_tier     = "db-g1-small"                            # 1.7GB memory, 1 shared core
  network_self_link = module.infrastructure.network_self_link  # From VPC module output

  # database_user_password is now auto-generated in the database module

  # Adjust other variables as needed for the dev environment
  maintenance_window_day  = 7     # Sunday
  maintenance_window_hour = 2     # 2 AM UTC for dev
  deletion_protection     = false # Dev can have deletion protection off
}

module "vpc_connector" {
  source = "../../modules/vpc-connector"

  name          = "${var.app_name}-${var.environment}-connector"
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

  cpu_limit               = "2"   # Increased for scheduler operations
  memory_limit            = "4Gi" # Increased for scheduler operations
  concurrency             = 100
  min_instances           = 1   # Ensure availability for scheduler jobs
  max_instances           = 3   # Increased for scheduler operations
  request_timeout_seconds = 300 # Increased for scheduler operations

  # Assuming /health is the correct endpoint for trackrat-api
  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id       = module.vpc_connector.id # Reference the VPC connector we created
  enable_cloudsql_access = true                    # Enable Cloud SQL access permissions

  # Environment variables (non-sensitive)
  environment_variables = {
    APP_ENV                  = "development"
    TRACKCAST_ENV            = "dev"
    MODEL_PATH               = "/app/models"
    TRACKCAST_SCHEDULER_MODE = "cloud_native" # Enable cloud-native mode to disable internal scheduler
  }

  # Secret environment variables (sensitive data from Secret Manager)
  secret_environment_variables = {
    DATABASE_URL = "${module.infrastructure.database_url_secret_name}:latest"
    NJT_USERNAME = "${module.infrastructure.njt_username_secret_name}:latest"
    NJT_PASSWORD = "${module.infrastructure.njt_password_secret_name}:latest"
  }

  # If a specific service account is already created for the API for this env:
  # service_account_email = "existing-sa@${var.project_id}.iam.gserviceaccount.com"

  # Custom domain (optional for dev, more likely for prod)
  # enable_custom_domain   = true
  # custom_domain_name     = "api.dev.example.com" # Replace with actual domain

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

# Service account for Cloud Scheduler jobs to invoke API service
resource "google_service_account" "scheduler_sa" {
  project      = var.project_id
  account_id   = "trackrat-scheduler-dev"
  display_name = "TrackRat Scheduler Service Account (Dev)"
  description  = "Service account for Cloud Scheduler jobs to invoke API service"
}

# Grant the scheduler service account permission to invoke the API service
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  service  = module.trackrat_api_service.service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# Direct Cloud Scheduler jobs targeting API service (Phase 3: Cloud-native scheduler)
resource "google_cloud_scheduler_job" "operations_jobs" {
  for_each = {
    data_collection = {
      schedule    = "0 * * * *" # Every hour at :00
      endpoint    = "/api/ops/collect-data"
      description = "Hourly data collection from NJ Transit and Amtrak APIs"
    }
    feature_processing = {
      schedule    = "10 * * * *" # Every hour at :10
      endpoint    = "/api/ops/process-features"
      description = "Hourly feature processing for collected train data"
    }
    prediction_generation = {
      schedule    = "20 * * * *" # Every hour at :20
      endpoint    = "/api/ops/generate-predictions"
      description = "Hourly track prediction generation for upcoming trains"
    }
  }

  project          = var.project_id
  region           = var.region
  name             = "trackrat-ops-${each.key}-dev"
  description      = each.value.description
  schedule         = each.value.schedule
  time_zone        = "America/New_York"
  attempt_deadline = "300s"

  http_target {
    uri         = "${module.trackrat_api_service.service_url}${each.value.endpoint}"
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      "operation"    = each.key
      "triggered_by" = "cloud_scheduler"
      "environment"  = "development"
    }))

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
      audience              = module.trackrat_api_service.service_url
    }
  }

  depends_on = [
    module.trackrat_api_service,
    google_service_account.scheduler_sa
  ]
}
