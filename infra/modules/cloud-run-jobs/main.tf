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

  # Extract unique secret names for IAM binding
  secret_names = toset([
    for v in var.secret_environment_variables : split(":", v)[0]
  ])
}

# Create Cloud Run Jobs for each operation
resource "google_cloud_run_v2_job" "operation_jobs" {
  for_each = var.jobs

  project  = var.project_id
  location = var.location
  name     = "${var.job_name_prefix}-${each.key}"
  labels   = var.labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      timeout               = each.value.task_timeout
      service_account       = var.service_account_email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      max_retries           = each.value.max_retries

      dynamic "vpc_access" {
        for_each = var.vpc_connector_id != null ? [1] : []
        content {
          connector = var.vpc_connector_id
          egress    = "ALL_TRAFFIC"
        }
      }

      containers {
        image = var.container_image

        # Set the command for this specific job
        command = each.value.command
        args    = each.value.args

        dynamic "env" {
          for_each = concat(
            [for k, v in var.environment_variables : { name = k, value = v }],
            [for k, v in each.value.environment_variables : { name = k, value = v }],
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
            cpu    = each.value.cpu_limit
            memory = each.value.memory_limit
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      # Prevent drift from manual job executions
      client,
      client_version,
    ]
  }

  depends_on = [
    google_secret_manager_secret_iam_member.job_secret_access
  ]
}

# Grant service account access to required secrets
resource "google_secret_manager_secret_iam_member" "job_secret_access" {
  for_each = local.secret_names

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}

# Grant service account permission to invoke these specific jobs
resource "google_cloud_run_v2_job_iam_member" "job_invoker" {
  for_each = google_cloud_run_v2_job.operation_jobs

  project  = var.project_id
  location = each.value.location
  name     = each.value.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}