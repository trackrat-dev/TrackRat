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

module "database" {
  source = "../../modules/database"

  project_id                    = var.project_id
  region                        = var.region
  instance_name                 = "${var.app_name}-${var.environment}-sql"
  instance_tier                 = "db-f1-micro"
  network_self_link             = module.infrastructure.network_self_link
  service_networking_connection = module.infrastructure.service_networking_connection

  # Alert notification emails
  critical_alert_email = var.critical_alert_email
  warning_alert_email  = var.warning_alert_email

  # Adjust other variables as needed for the staging environment
  maintenance_window_day  = 7     # Sunday
  maintenance_window_hour = 2     # 2 AM UTC for staging
  deletion_protection     = false # Staging can have deletion protection off
}

module "vpc_connector" {
  source = "../../modules/vpc-connector"

  name          = "${var.app_name}-${var.environment}-vpc"
  region        = var.region
  network_name  = module.infrastructure.vpc_network_name
  ip_cidr_range = "10.2.2.0/28" # Dedicated /28 range for staging VPC connector
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
  max_instances           = 2
  request_timeout_seconds = 60

  startup_probe_path            = "/health"
  liveness_probe_path           = "/health"
  liveness_probe_period_seconds = 30

  vpc_connector_id       = module.vpc_connector.id
  enable_cloudsql_access = true

  # Environment variables (non-sensitive)
  environment_variables = {
    APP_ENV                  = "staging"
    TRACKCAST_ENV            = "staging"
    MODEL_PATH               = "/app/models"
    TRACKCAST_SCHEDULER_MODE = "cloud_native"
  }

  # Secret environment variables (sensitive data from Secret Manager)
  secret_environment_variables = {
    DATABASE_URL = "${module.database.database_url_secret_name}:latest"
    NJT_USERNAME = "${module.infrastructure.njt_username_secret_name}:latest"
    NJT_PASSWORD = "${module.infrastructure.njt_password_secret_name}:latest"
  }

  # Custom domain configuration
  enable_custom_domain = var.enable_custom_domain
  custom_domain_name   = var.custom_domain_name

  labels = {
    service = "trackrat-api"
    env     = "staging"
  }

  depends_on = [
    module.database,
    module.vpc_connector,
    module.infrastructure
  ]
}

# Service account for Cloud Scheduler jobs to invoke Cloud Run Jobs
resource "google_service_account" "scheduler_sa" {
  project      = var.project_id
  account_id   = "trackrat-scheduler-staging"
  display_name = "TrackRat Scheduler Service Account (Staging)"
  description  = "Service account for Cloud Scheduler jobs to invoke Cloud Run Jobs"
}

# Cloud Run Jobs for scheduled operations
module "scheduled_operations" {
  source = "../../modules/cloud-run-jobs"

  project_id            = var.project_id
  location              = var.region
  job_name_prefix       = "trackrat-ops-staging"
  container_image       = var.api_image_url
  service_account_email = google_service_account.scheduler_sa.email
  vpc_connector_id      = module.vpc_connector.id

  # Global environment variables for all jobs
  environment_variables = {
    APP_ENV                  = "staging"
    TRACKCAST_ENV            = "staging"
    MODEL_PATH               = "/app/models"
    TRACKCAST_SCHEDULER_MODE = "cloud_native"
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
    data-collection = {
      command      = ["trackcast", "collect-data"]
      cpu_limit    = "1"
      memory_limit = "512Mi"
      max_retries  = 2
      task_timeout = "60s"
      environment_variables = {
        JOB_TYPE = "data_collection"
      }
    }

    feature-processing = {
      command      = ["trackcast", "process-features"]
      cpu_limit    = "1"
      memory_limit = "512Mi"
      max_retries  = 1
      task_timeout = "60s"
      environment_variables = {
        JOB_TYPE = "feature_processing"
      }
    }

    prediction-generation = {
      command      = ["trackcast", "generate-predictions"]
      cpu_limit    = "1"
      memory_limit = "512Mi"
      max_retries  = 1
      task_timeout = "60s"
      environment_variables = {
        JOB_TYPE = "prediction_generation"
      }
    }
  }

  labels = {
    environment = "staging"
    component   = "scheduler"
  }

  depends_on = [
    module.database,
    module.vpc_connector,
    module.infrastructure
  ]
}

# Cloud Scheduler jobs targeting Cloud Run Jobs
resource "google_cloud_scheduler_job" "operations" {
  for_each = {
    data-collection = {
      schedule    = "0,15,30,45 * * * *" # Every 15 minutes at :00, :15, :30, :45
      description = "Data collection from NJ Transit and Amtrak APIs every 15 minutes"
      job_name    = "data-collection"
    }
    feature-processing = {
      schedule    = "5,20,35,50 * * * *" # Every 15 minutes at :05, :20, :35, :50
      description = "Feature processing for collected train data every 15 minutes"
      job_name    = "feature-processing"
    }
    prediction-generation = {
      schedule    = "10,25,40,55 * * * *" # Every 15 minutes at :10, :25, :40, :55
      description = "Track prediction generation for upcoming trains every 15 minutes"
      job_name    = "prediction-generation"
    }
  }

  project          = var.project_id
  region           = var.region
  name             = "trackrat-ops-staging-${each.value.job_name}-scheduler-trigger"
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
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/trackrat-ops-staging-${each.value.job_name}:run"
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
