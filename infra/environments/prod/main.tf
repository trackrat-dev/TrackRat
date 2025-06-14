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
