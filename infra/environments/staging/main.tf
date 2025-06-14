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

  project_id  = var.project_id
  region      = var.region
  zone        = var.zone
  environment = "staging"
  app_name    = "trackrat"
  vpc_cidr    = "10.2.0.0/16"
  subnet_cidr = "10.2.1.0/24"
  db_password = var.db_password # Pass the environment's db_password
}

module "database" {
  source = "../../modules/database"

  project_id        = var.project_id
  region            = var.region
  instance_name     = "${var.app_name}-${var.environment}-sql"
  network_self_link = module.infrastructure.network_self_link

  database_user_password = var.db_password

  # Staging specific settings (can be adjusted)
  instance_tier           = "db-g1-small" # Example: slightly larger than dev
  maintenance_window_day  = 6             # Saturday
  maintenance_window_hour = 4             # 4 AM UTC
  deletion_protection     = true          # Enable for staging
  # backup_window_start_time = "04:00" # Specific backup time for staging if needed
  # enable_cloud_sql_insights = true
  # slow_query_log_min_duration = 250
  # log_connections = true # Be cautious in prod
  # log_disconnections = true # Be cautious in prod
}

module "trackrat_api_service_staging" { # Changed module name to avoid conflict if environments are ever merged/referenced
  source = "../../modules/cloud-run"

  project_id      = var.project_id
  location        = var.region # Assuming 'region' is defined in staging/variables.tf
  service_name    = "trackrat-api-staging"
  container_image = var.api_image_url_staging # Use a staging-specific image var
  container_port  = 8000

  cpu_limit               = "1"
  memory_limit            = "1Gi" # Slightly more memory for staging if needed
  concurrency             = 100
  min_instances           = 0 # For dev/staging
  max_instances           = 2
  request_timeout_seconds = 60

  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id = var.vpc_connector_id_staging # Staging specific connector

  environment_variables = {
    APP_ENV  = "staging"
    GIN_MODE = "release"
    # Add other non-sensitive configs for staging
  }

  # secret_environment_variables = {
  #   DATABASE_URL = "staging-db-secret:latest"
  #   API_KEY      = "staging-api-key-secret:1"
  # }

  # enable_custom_domain   = true
  # custom_domain_name     = "api.staging.example.com"

  labels = {
    service = "trackrat-api"
    env     = "staging"
  }

  depends_on = []
}

module "trackrat_scheduler_staging" {
  source = "../../modules/scheduler"

  project_id      = var.project_id
  location        = var.region
  service_name    = "trackrat-scheduler-staging"
  container_image = var.scheduler_image_url_staging # Staging specific image var

  min_instances = 0 # For staging

  scheduler_job_name  = "invoke-trackrat-scheduler-staging"
  scheduler_schedule  = "0 3 * * *" # Example: Every day at 3 AM (staging)
  scheduler_http_path = "/run-tasks"

  # vpc_connector_id = var.vpc_connector_id_staging # If needed

  environment_variables = {
    APP_ENV = "staging"
  }

  # secret_environment_variables = {
  #   SOME_SCHEDULER_SECRET = "scheduler-secret-staging:latest"
  # }

  labels = {
    service = "trackrat-scheduler"
    env     = "staging"
  }

  depends_on = [
    module.trackrat_api_service_staging
  ]
}
