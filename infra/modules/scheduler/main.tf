terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  secret_env_vars = [
    for k, v in var.secret_environment_variables : {
      name = k
      value_source = {
        secret_key_ref = {
          secret  = split(":", v)[0]
          version = split(":", v)[1]
        }
      }
    }
  ]
}

resource "google_cloud_run_v2_service" "scheduler_service" {
  project  = var.project_id
  location = var.location
  name     = var.service_name
  labels   = var.labels

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances # Should be 1 as per requirement
    }

    dynamic "vpc_access" {
      for_each = var.vpc_connector_id != null ? [1] : []
      content {
        connector = var.vpc_connector_id
        egress    = "ALL_TRAFFIC"
      }
    }

    timeout                          = "${var.request_timeout_seconds}s"
    service_account                  = local.cloud_run_sa_email # Defined in iam.tf
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = 1 # Ensure only one request at a time for scheduler

    containers {
      image = var.container_image
      ports {
        container_port = var.container_port
      }
      dynamic "env" {
        for_each = concat(
          [for k, v in var.environment_variables : { name = k, value = v }],
          local.secret_env_vars
        )
        content {
          name  = env.value.name
          value = try(env.value.value, null)
          dynamic "value_source" {
            for_each = try(env.value.value_source, null) != null ? [env.value.value_source] : []
            content {
              secret_key_ref {
                secret  = value_source.value.secret_key_ref.secret
                version = value_source.value.secret_key_ref.version
              }
            }
          }
        }
      }
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
      }
      # No health probes defined for scheduler in issue, can be added if an endpoint exists
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_service_account.cloud_run_sa # Defined in iam.tf
  ]
}

# Legacy scheduler job (backward compatibility)
resource "google_cloud_scheduler_job" "scheduler_job" {
  count = var.legacy_scheduler_enabled && var.scheduler_schedule != null ? 1 : 0

  project          = var.project_id
  region           = var.location # Scheduler jobs are regional
  name             = var.scheduler_job_name
  description      = var.scheduler_job_description
  schedule         = var.scheduler_schedule
  time_zone        = var.scheduler_timezone
  attempt_deadline = "320s" # How long to wait for the job to complete, should be less than timeout

  http_target {
    uri         = google_cloud_run_v2_service.scheduler_service.uri # Target the deployed Cloud Run service
    http_method = "POST"                                            # Or GET, depending on the scheduler endpoint
    body        = base64encode("{\"data\":\"scheduled_run\"}")      # Example body, if needed

    oidc_token {
      service_account_email = local.scheduler_job_sa_email # SA for invoking Cloud Run, defined in iam.tf
      audience              = google_cloud_run_v2_service.scheduler_service.uri
    }
  }

  depends_on = [
    google_cloud_run_v2_service.scheduler_service,
    google_service_account.scheduler_job_sa
  ]
}

# New high-frequency scheduler jobs
resource "google_cloud_scheduler_job" "operations_jobs" {
  for_each = var.scheduler_jobs

  project          = var.project_id
  region           = var.location
  name             = "${var.scheduler_job_name}-${each.key}"
  description      = each.value.description
  schedule         = each.value.schedule
  time_zone        = var.scheduler_timezone
  attempt_deadline = "300s" # Shorter timeout for individual operations

  http_target {
    # Target API service instead of scheduler service for operations
    uri         = var.api_service_uri != null ? "${var.api_service_uri}${each.value.endpoint}" : "${google_cloud_run_v2_service.scheduler_service.uri}${each.value.endpoint}"
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      "operation" : each.key,
      "triggered_by" : "cloud_scheduler",
      "timestamp" : timestamp()
    }))

    oidc_token {
      service_account_email = local.scheduler_job_sa_email
      # Use appropriate audience based on target service
      audience = var.api_service_uri != null ? var.api_service_uri : google_cloud_run_v2_service.scheduler_service.uri
    }
  }

  depends_on = [
    google_service_account.scheduler_job_sa
  ]
}
