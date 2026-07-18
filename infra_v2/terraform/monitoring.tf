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

# Newly created log-based metrics aren't immediately queryable by the monitoring
# backend; the alert policy create call returns 404 until the metric propagates.
# GCP docs say "up to 10 minutes"; in practice 60s is reliably enough.
resource "time_sleep" "wait_provider_auth_metric" {
  count = var.environment == "production" ? 1 : 0

  depends_on      = [google_logging_metric.provider_auth_failures]
  create_duration = "60s"

  triggers = {
    metric_name = google_logging_metric.provider_auth_failures[0].name
  }
}

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

  depends_on = [
    google_project_service.apis["monitoring.googleapis.com"],
    time_sleep.wait_provider_auth_metric,
  ]
}

# Alert policies - data disk utilization on the persistent disk.
# Backed by google_logging_metric.data_disk_usage_percent (see metrics.tf),
# populated by SchedulerService.check_resource_usage every 15 minutes.
# Two tiers (warn at 75%, page at 85%) so slow growth is caught well before
# the disk fills silently, as happened in issue #1344.
resource "time_sleep" "wait_disk_usage_metric" {
  count = var.environment == "production" ? 1 : 0

  depends_on      = [google_logging_metric.data_disk_usage_percent]
  create_duration = "60s"

  triggers = {
    metric_name = google_logging_metric.data_disk_usage_percent[0].name
  }
}

resource "google_monitoring_alert_policy" "data_disk_usage_warning" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Data Disk Usage Warning (75%)"
  combiner     = "OR"

  conditions {
    display_name = "Data disk usage above 75%"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.data_disk_usage_percent[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 75
      duration        = "0s"

      # data_disk_usage_percent is a DELTA/DISTRIBUTION logs metric. ALIGN_MEAN
      # is invalid on distributions; ALIGN_DELTA aggregates the window into a
      # distribution and REDUCE_MEAN reduces it to the exact mean (a DOUBLE).
      aggregations {
        alignment_period     = "1800s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.apis["monitoring.googleapis.com"],
    time_sleep.wait_disk_usage_metric,
  ]
}

resource "google_monitoring_alert_policy" "data_disk_usage_critical" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Data Disk Usage Critical (85%)"
  combiner     = "OR"

  conditions {
    display_name = "Data disk usage above 85%"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.data_disk_usage_percent[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 85
      duration        = "0s"

      # data_disk_usage_percent is a DELTA/DISTRIBUTION logs metric. ALIGN_MEAN
      # is invalid on distributions; ALIGN_DELTA aggregates the window into a
      # distribution and REDUCE_MEAN reduces it to the exact mean (a DOUBLE).
      aggregations {
        alignment_period     = "1800s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.apis["monitoring.googleapis.com"],
    time_sleep.wait_disk_usage_metric,
  ]
}

# Alert policy - per-table vacuum/analyze health on the high-churn tables
# (journey_stops, train_journeys, segment_transit_times). Backed by
# google_logging_metric.table_dead_tuple_ratio_pct (see metrics.tf), populated
# by SchedulerService.check_resource_usage every 15 minutes. Added after
# journey_stops went its entire lifetime with zero completed vacuum/analyze
# passes, silently bloating until a query started timing out in production
# (issue #1359) — this catches the same drift automatically going forward.
resource "time_sleep" "wait_vacuum_health_metric" {
  count = var.environment == "production" ? 1 : 0

  depends_on      = [google_logging_metric.table_dead_tuple_ratio_pct]
  create_duration = "60s"

  triggers = {
    metric_name = google_logging_metric.table_dead_tuple_ratio_pct[0].name
  }
}

resource "google_monitoring_alert_policy" "table_vacuum_health" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Table Vacuum Health (dead tuples > 30%)"
  combiner     = "OR"

  conditions {
    display_name = "Dead tuple ratio above 30% on a monitored table"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.table_dead_tuple_ratio_pct[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 30
      duration        = "0s"

      # table_dead_tuple_ratio_pct is a DELTA/DISTRIBUTION logs metric. Neither
      # ALIGN_MEAN nor REDUCE_MAX is valid on distributions; ALIGN_DELTA +
      # REDUCE_MEAN grouped by table_name yields each table's exact mean ratio
      # (a DOUBLE), so the condition fires if any single table exceeds 30%.
      aggregations {
        alignment_period     = "1800s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["metric.label.table_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.apis["monitoring.googleapis.com"],
    time_sleep.wait_vacuum_health_metric,
  ]
}

# Alert policy - fires when NJT stop-ordering warnings spike.
# Backed by google_logging_metric.stop_order_warnings (see metrics.tf).
# Both origin_station_not_first and stops_missing_scheduled_times fire per
# journey per collection; a low baseline is expected (a discovery-created stop
# legitimately lacks scheduled times for one cycle), so the threshold sits well
# above that baseline over a 30-minute window (two NJT collection cycles). A
# sustained spike — or the origin-displacement regression behind #1530 that hits
# many trains at once — pages, while occasional single occurrences do not.
resource "time_sleep" "wait_stop_order_metric" {
  count = var.environment == "production" ? 1 : 0

  depends_on      = [google_logging_metric.stop_order_warnings]
  create_duration = "60s"

  triggers = {
    metric_name = google_logging_metric.stop_order_warnings[0].name
  }
}

resource "google_monitoring_alert_policy" "stop_order_warnings" {
  count = var.environment == "production" ? 1 : 0

  display_name = "NJT Stop-Order Warnings (spike)"
  combiner     = "OR"

  conditions {
    display_name = "Stop-ordering warnings above baseline"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.stop_order_warnings[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 15
      duration        = "0s"

      # stop_order_warnings is a DELTA/INT64 counter. ALIGN_SUM totals every
      # warning event within the 30-minute window (ALIGN_DELTA only reports the
      # boundary-bucket change, which can undercount a sustained spike); REDUCE_SUM
      # then folds both events into one count. Mirrors the provider_auth_failures
      # policy exactly, so the condition fires on the aggregate ordering-warning
      # rate regardless of which event dominates.
      aggregations {
        alignment_period     = "1800s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.apis["monitoring.googleapis.com"],
    time_sleep.wait_stop_order_metric,
  ]
}
