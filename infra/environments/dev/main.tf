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
}

module "database" {
  source = "../../modules/database"

  project_id    = var.project_id
  region        = var.region
  instance_name = "${var.app_name}-${var.environment}-sql" # Example instance name
  # instance_tier      = "db-f1-micro" # Or use module default / specify per env
  network_self_link = module.infrastructure.network_self_link # From VPC module output

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

  cpu_limit               = "1"     # As per issue: 1-2 vCPUs
  memory_limit            = "512Mi" # As per issue: 512MB-2GB
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

  # Example environment variables
  environment_variables = {
    APP_ENV  = "development"
    GIN_MODE = "debug"
    # Add other non-sensitive configs
  }

  # Example secret environment variables
  # secret_environment_variables = {
  #   DATABASE_URL = "my-db-secret-name:latest" # Replace with actual secret name and version
  #   API_KEY      = "my-api-key-secret:1"
  # }

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
    # Add dependencies if any, e.g., module.vpc_connector if defined in this file
    # module.artifact_registry if image is built and pushed by another terraform module here
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
  min_instances = 0 # For dev

  # request_timeout_seconds is 3600 (1 hour) by default in module

  scheduler_job_name = "invoke-trackrat-scheduler-dev"
  scheduler_schedule = "0 2 * * *" # Example: Every day at 2 AM

  # vpc_connector_id = var.vpc_connector_id # If scheduler needs to access VPC resources

  environment_variables = {
    APP_ENV = "development"
    # Add other scheduler-specific non-sensitive environment variables
  }

  # secret_environment_variables = {
  #   SOME_SCHEDULER_SECRET = "scheduler-secret-name:latest"
  # }

  labels = {
    service = "trackrat-scheduler"
    env     = "dev"
  }

  depends_on = [
    module.trackrat_api_service # Example: if scheduler depends on API being up (e.g. for service discovery)
  ]
}
