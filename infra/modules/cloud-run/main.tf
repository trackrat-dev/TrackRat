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

resource "google_cloud_run_v2_service" "default" {
  project     = var.project_id
  location    = var.location
  name        = var.service_name
  labels      = var.labels
  annotations = var.annotations
  ingress     = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Remove volumes block - Cloud SQL connection will be handled via VPC connector
    # volumes {
    #   name = "cloudsql"
    #   cloud_sql_instance {
    #     instances = [] # To be populated if Cloud SQL direct connection is used without proxy
    #   }
    # }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC" # Necessary for private IP for Cloud SQL
    }

    timeout                          = "${var.request_timeout_seconds}s"
    service_account                  = local.effective_service_account_email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = var.concurrency
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
        startup_cpu_boost = true # Enable CPU boost at startup
      }

      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 6
        http_get {
          path = var.startup_probe_path
          port = var.container_port
        }
      }

      liveness_probe {
        initial_delay_seconds = 15 # Give some time for startup
        timeout_seconds       = 5
        period_seconds        = var.liveness_probe_period_seconds
        failure_threshold     = 3
        http_get {
          path = var.liveness_probe_path
          port = var.container_port
        }
      }
    }
    # Graceful shutdown is handled by Cloud Run sending SIGTERM.
    # The application needs to handle SIGTERM.
    # The 'timeout_seconds' in 'template' block also acts as a general request processing timeout.
    # Cloud Run's default termination period is 10 minutes. If the app needs less, it should exit sooner on SIGTERM.
    # The `var.graceful_shutdown_timeout_seconds` is more of an application-level concern for SIGTERM handling duration.
    # No direct Terraform setting for SIGTERM timeout other than the main service timeout.
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      # If autoscaling.knative.dev/maxScale is used, this can cause conflicts if not ignored.
      annotations["autoscaling.knative.dev/maxScale"],
    ]
  }

  depends_on = [
    google_service_account.default,
  ]
}
