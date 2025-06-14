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
      name  = k
      value_source = {
        secret_key_ref = {
          secret  = split(":", v)[0]
          version = split(":", v)[1]
        }
      }
    }
  ]
  actual_subscription_name = var.pubsub_subscription_name == "" ? "sub-${var.service_name}-${var.pubsub_topic_name}" : var.pubsub_subscription_name

  // These should align with what's in iam.tf
  cloud_run_sa_email   = var.collector_service_account_email == null ? google_service_account.cloud_run_sa[0].email : var.collector_service_account_email
  pubsub_push_sa_email = google_service_account.pubsub_push_sa.email // This was defined in iam.tf
}

resource "google_cloud_run_v2_service" "collector_service" {
  project  = var.project_id
  location = var.location
  name     = var.service_name
  labels   = var.labels

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = var.vpc_connector_id != null ? "ALL_TRAFFIC" : "PRIVATE_RANGES_ONLY"
    }

    timeout                         = "${var.request_timeout_seconds}s"
    service_account                 = local.cloud_run_sa_email # Defined in iam.tf
    execution_environment           = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = var.concurrency_per_instance

    containers {
      image = var.container_image
      ports {
        container_port = var.container_port // Pub/Sub push sends POST to this port
      }
      env = concat(
        [for k, v in var.environment_variables : { name = k, value = v }],
        local.secret_env_vars
      )
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
      }
      // No health probes typically needed for Pub/Sub triggered services unless they also serve HTTP
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_service_account.cloud_run_sa // Defined in iam.tf
  ]
}

// Assumes Pub/Sub topic (projects/{project_id}/topics/{var.pubsub_topic_name}) already exists.
// The Pub/Sub service account (local.pubsub_pusher_sa_email) needs 'roles/pubsub.publisher' on the topic
// and the Cloud Run service SA (local.cloud_run_sa_email) needs 'roles/run.invoker'.
// Actually, for Pub/Sub push subscriptions, we need a special Pub/Sub SA to be granted invoker.

resource "google_pubsub_subscription" "default" {
  project = var.project_id
  name    = local.actual_subscription_name
  topic   = "projects/${var.project_id}/topics/${var.pubsub_topic_name}" // Ensure full topic path

  ack_deadline_seconds = var.ack_deadline_seconds

  push_config {
    push_endpoint = google_cloud_run_v2_service.collector_service.uri // HTTPS endpoint of the service
    oidc_token {
      service_account_email = local.pubsub_push_sa_email // This SA is used by Pub/Sub to authenticate to Cloud Run. Defined in iam.tf
      audience              = google_cloud_run_v2_service.collector_service.uri
    }
    // Pub/Sub automatically wraps message in a JSON payload:
    // { "message": { "data": "BASE64_ENCODED_DATA", ... }, "subscription": "..." }
  }

  retry_policy {
    minimum_backoff = var.retry_policy.minimum_backoff
    maximum_backoff = var.retry_policy.maximum_backoff
  }

  depends_on = [
    google_cloud_run_v2_service.collector_service,
    google_service_account.pubsub_push_sa,
    google_service_account_iam_member.pubsub_sa_token_creator // Explicitly add this
  ]
}
