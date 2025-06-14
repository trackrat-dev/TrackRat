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

  project_id         = var.project_id
  region             = var.region
  instance_name      = "\${var.app_name}-\${var.environment}-sql"
  network_self_link  = module.infrastructure.network_self_link

  database_user_password = var.db_password

  # Staging specific settings (can be adjusted)
  instance_tier           = "db-g1-small" # Example: slightly larger than dev
  maintenance_window_day  = 6 # Saturday
  maintenance_window_hour = 4 # 4 AM UTC
  deletion_protection    = true # Enable for staging
  # backup_window_start_time = "04:00" # Specific backup time for staging if needed
  # enable_cloud_sql_insights = true
  # slow_query_log_min_duration = 250
  # log_connections = true # Be cautious in prod
  # log_disconnections = true # Be cautious in prod
}
