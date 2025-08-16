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
  source              = "./modules/secrets"
  app_name            = var.app_name
  environment         = var.environment
  nj_transit_username = var.nj_transit_username
  nj_transit_password = var.nj_transit_password
  nj_transit_token    = var.nj_transit_token
  amtrak_api_key      = var.amtrak_api_key
  apns_team_id        = var.apns_team_id
  apns_key_id         = var.apns_key_id
  apns_auth_key       = var.apns_auth_key

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

# Create GCS bucket for database backups
resource "google_storage_bucket" "db_backup" {
  name     = "${var.app_name}-${var.environment}-periodic-db-backup"
  location = var.region

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }

  # Enable versioning for backup history
  versioning {
    enabled = true
  }

  # Lifecycle management for backups
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  # Lifecycle rule for versioned objects
  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }

  # Enable uniform bucket-level access
  uniform_bucket_level_access = true

  depends_on = [module.apis]
}

# Create VPC Connector for Cloud Run private networking
module "vpc_connector" {
  source        = "./modules/vpc-connector"
  name          = "${var.app_name}-${var.environment}-vpc"
  region        = var.region
  network_name  = module.vpc.network_name
  ip_cidr_range = var.vpc_connector_cidr

  depends_on = [module.vpc]
}

# Create Cloud SQL PostgreSQL database
module "database" {
  source                      = "./modules/database"
  project_id                  = var.project_id
  region                      = var.region
  instance_name               = "${var.app_name}-${var.environment}-db"
  database_version            = "POSTGRES_17"
  instance_tier               = "db-g1-small"
  network_self_link           = module.vpc.network_self_link
  service_networking_connection = module.vpc.service_networking_connection

  depends_on = [module.vpc]
}
