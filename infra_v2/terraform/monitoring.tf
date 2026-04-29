# Uptime Monitoring (Production Only)

# Email notification channel
resource "google_monitoring_notification_channel" "email" {
  count = var.environment == "production" ? 1 : 0

  display_name = "TrackRat Alerts"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Uptime check - monitors /health/ready endpoint
resource "google_monitoring_uptime_check_config" "api_health" {
  count = var.environment == "production" ? 1 : 0

  display_name = "trackrat-api-health"
  timeout      = "10s"
  period       = "60s"

  selected_regions = ["USA_OREGON", "USA_IOWA", "USA_VIRGINIA"]

  http_check {
    path         = "/health/ready"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.domain
    }
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Alert policy - fires after 2 consecutive check failures
resource "google_monitoring_alert_policy" "api_unavailable" {
  count = var.environment == "production" ? 1 : 0

  display_name = "API Unavailable"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failing"

    condition_threshold {
      filter          = "resource.type = \"uptime_url\" AND metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id = \"${google_monitoring_uptime_check_config.api_health[0].uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "120s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_NEXT_OLDER"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Alert policy - fires when upstream-provider auth failures exceed threshold.
# Backed by google_logging_metric.provider_auth_failures (see metrics.tf).
# Threshold of 3 failures over 5 minutes debounces against one-off blips
# while still firing within ~5 minutes of a genuine token expiry.
resource "google_monitoring_alert_policy" "provider_auth_failure" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Provider API Auth Failure"
  combiner     = "OR"

  conditions {
    display_name = "Provider auth errors detected"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.provider_auth_failures[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}
