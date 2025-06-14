# Production environment configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "trackrat-prod-terraform-state"
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
  environment = "prod"
  app_name    = "trackrat"
  vpc_cidr    = "10.3.0.0/16"
  subnet_cidr = "10.3.1.0/24"
  db_password = var.db_password # Pass the environment's db_password
}

module "database" {
  source = "../../modules/database"

  project_id        = var.project_id
  region            = var.region
  instance_name     = "${var.app_name}-${var.environment}-sql"
  network_self_link = module.infrastructure.network_self_link

  database_user_password = var.db_password

  # Production specific settings
  instance_tier               = "db-standard-1" # Example: Production tier
  maintenance_window_day      = 7               # Sunday (choose off-peak)
  maintenance_window_hour     = 6               # 6 AM UTC (choose off-peak)
  deletion_protection         = true
  backup_window_start_time    = "05:00" # Specific backup time for prod
  enable_cloud_sql_insights   = true
  slow_query_log_min_duration = 100 # Log queries longer than 100ms
  # log_connections = false # Typically too verbose for prod unless debugging
  # log_disconnections = false # Typically too verbose for prod unless debugging
}

module "trackrat_api_service_prod" { # Changed module name
  source = "../../modules/cloud-run"

  project_id      = var.project_id
  location        = var.region             # Assuming 'region' is defined in prod/variables.tf
  service_name    = "trackrat-api-prod"    # Prod service name
  container_image = var.api_image_url_prod # Prod image var
  container_port  = 8000

  cpu_limit               = "2"   # Prod: 1-2 vCPUs, using 2 for higher capacity
  memory_limit            = "2Gi" # Prod: 512MB-2GB, using 2GB for higher capacity
  concurrency             = 100
  min_instances           = 1 # For Prod
  max_instances           = 2 # Max 2 as per issue, can be increased based on load
  request_timeout_seconds = 60

  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id = var.vpc_connector_id_prod # Prod specific connector

  environment_variables = {
    APP_ENV  = "production"
    GIN_MODE = "release"
    # Add other non-sensitive configs for production
  }

  # secret_environment_variables = {
  #   DATABASE_URL = "prod-db-secret:latest"
  #   API_KEY      = "prod-api-key-secret:1"
  # }

  enable_custom_domain = true              # Typically true for prod
  custom_domain_name   = "api.example.com" # Replace with actual prod domain

  labels = {
    service = "trackrat-api"
    env     = "prod"
  }

  depends_on = []
}

module "trackrat_scheduler_prod" {
  source = "../../modules/scheduler"

  project_id      = var.project_id
  location        = var.region
  service_name    = "trackrat-scheduler-prod"
  container_image = var.scheduler_image_url_prod # Prod specific image var

  # min_instances = 1 # Consider for prod if cold starts are an issue, module default is 0.
  # For a scheduler that runs periodically, 0 might be fine to save costs.

  scheduler_job_name  = "invoke-trackrat-scheduler-prod"
  scheduler_schedule  = "0 4 * * *" # Example: Every day at 4 AM (prod)
  scheduler_http_path = "/run-tasks"

  # vpc_connector_id = var.vpc_connector_id_prod # If needed

  environment_variables = {
    APP_ENV = "production"
  }

  # secret_environment_variables = {
  #   SOME_SCHEDULER_SECRET = "scheduler-secret-prod:latest"
  # }

  labels = {
    service = "trackrat-scheduler"
    env     = "prod"
  }

  depends_on = [
    module.trackrat_api_service_prod
  ]
}
