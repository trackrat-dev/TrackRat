terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Configure the Google Cloud Provider for beta resources
provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Enable required APIs
module "apis" {
  source     = "./modules/apis"
  project_id = var.project_id
}

# Create VPC and networking
module "vpc" {
  source      = "./modules/vpc"
  app_name    = var.app_name
  environment = var.environment
  region      = var.region
  subnet_cidr = var.subnet_cidr

  depends_on = [module.apis]
}

# Create Secret Manager resources
module "secrets" {
  source      = "./modules/secrets"
  app_name    = var.app_name
  environment = var.environment

  depends_on = [module.apis]
}

# Create Artifact Registry
module "artifact_registry" {
  source      = "./modules/artifact-registry"
  app_name    = var.app_name
  environment = var.environment
  region      = var.region

  depends_on = [module.apis]
}
