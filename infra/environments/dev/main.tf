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

  cpu_limit               = "1"   # As per issue: 1-2 vCPUs
  memory_limit            = "2Gi" # Ensure 2GB of RAM
  concurrency             = 100
  min_instances           = 0 # For dev/staging
  max_instances           = 2 # As per issue
  request_timeout_seconds = 60

  # Assuming /health is the correct endpoint for trackrat-api
  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id       = module.vpc_connector.id # Reference the VPC connector we created
  enable_cloudsql_access = true                    # Enable Cloud SQL access permissions

  # Environment variables (non-sensitive)
  environment_variables = {
    APP_ENV       = "development"
    TRACKCAST_ENV = "dev"
    MODEL_PATH    = "/app/models"
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

module "trackrat_scheduler_dev" {
  source = "../../modules/scheduler"

  project_id      = var.project_id
  location        = var.region
  service_name    = "trackrat-scheduler-dev"
  container_image = var.scheduler_image_url # To be defined in variables.tf

  # Assuming scheduler runs on port 8080 by default as per module
  # container_port = 8080

  # max_instances is 1 by default in the module
  min_instances = 0     # For dev
  memory_limit  = "2Gi" # Ensure 2GB of RAM

  # request_timeout_seconds is 3600 (1 hour) by default in module

  scheduler_job_name = "invoke-trackrat-scheduler-dev"

  # Phase 2: Parallel operation - keep legacy scheduler alongside new jobs
  legacy_scheduler_enabled = true
  scheduler_schedule       = "0 2 * * *" # Keep existing daily job for now

  # Phase 1: New high-frequency scheduler jobs targeting API service
  api_service_uri = module.trackrat_api_service.service_url

  # Hourly scheduling as requested (Phase 1 implementation)
  scheduler_jobs = {
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

  # vpc_connector_id = var.vpc_connector_id # If scheduler needs to access VPC resources

  environment_variables = {
    APP_ENV = "development"
    # Phase 3: Enable cloud-native mode to disable internal scheduler
    # TRACKCAST_SCHEDULER_MODE = "cloud_native"
    # For now, keep internal scheduler running alongside new jobs (Phase 2)
  }

  # secret_environment_variables = {
  #   SOME_SCHEDULER_SECRET = "scheduler-secret-name:latest"
  # }

  labels = {
    service = "trackrat-scheduler"
    env     = "dev"
  }

  depends_on = [
    module.trackrat_api_service # API service must be deployed before scheduler jobs can target it
  ]
}
