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
