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
}
