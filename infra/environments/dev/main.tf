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
  db_password = var.db_password # Pass the environment's db_password to the main infrastructure module
}

module "database" {
  source = "../../modules/database"

  project_id    = var.project_id
  region        = var.region
  instance_name = "${var.app_name}-${var.environment}-sql" # Example instance name
  # instance_tier      = "db-f1-micro" # Or use module default / specify per env
  network_self_link = module.infrastructure.network_self_link # From VPC module output

  database_user_password = var.db_password # This variable needs to be defined in dev/variables.tf and sourced securely

  # Adjust other variables as needed for the dev environment
  maintenance_window_day  = 7     # Sunday
  maintenance_window_hour = 2     # 2 AM UTC for dev
  deletion_protection     = false # Dev can have deletion protection off
}
