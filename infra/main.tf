terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
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
  source                              = "./modules/vpc"
  app_name                            = var.app_name
  environment                         = var.environment
  region                              = var.region
  vpc_cidr                            = var.vpc_cidr
  subnet_cidr                         = var.subnet_cidr
  private_service_connection_ip_range = var.private_service_connection_ip_range

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
  source          = "./modules/artifact-registry"
  app_name        = var.app_name
  environment     = var.environment
  region          = var.region
  repository_name = var.artifact_registry_repository_name

  depends_on = [module.apis]
}
