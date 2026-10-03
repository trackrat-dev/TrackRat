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

# Alert policies - boot filesystem utilization on the VM's 10 GB boot disk.
# Backed by google_logging_metric.boot_disk_usage_percent (see metrics.tf),
# populated by SchedulerService.check_resource_usage every 15 minutes.
#
# Nothing watched this filesystem until issue #1826. The data-disk alerts above
# check settings.data_disk_path, explicitly not the boot disk, so when the boot
# disk filled on 2026-09-01 the data disk was healthy (~57%) and reported as
# such — the alerts were correct and silent while the machine was broken.
#
# Same 75%/85% tiers as the data disk. On a 10 GB boot disk filling at the
# observed rate (~10 GB over ~2 weeks) those leave roughly 3.5 and 2 days of
# warning respectively, which is the window this is for: Docker's log writing
# only breaks at 100%, so anything that pages before then is actionable.
resource "time_sleep" "wait_boot_disk_usage_metric" {
  count = var.environment == "production" ? 1 : 0

  depends_on      = [google_logging_metric.boot_disk_usage_percent]
  create_duration = "60s"

  triggers = {
    metric_name = google_logging_metric.boot_disk_usage_percent[0].name
  }
}

resource "google_monitoring_alert_policy" "boot_disk_usage_warning" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Boot Disk Usage Warning (75%)"
  combiner     = "OR"

  conditions {
    display_name = "Boot disk usage above 75%"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.boot_disk_usage_percent[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 75
      duration        = "0s"

      # boot_disk_usage_percent is a DELTA/DISTRIBUTION logs metric. ALIGN_MEAN
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
    time_sleep.wait_boot_disk_usage_metric,
  ]
}

resource "google_monitoring_alert_policy" "boot_disk_usage_critical" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Boot Disk Usage Critical (85%)"
  combiner     = "OR"

  conditions {
    display_name = "Boot disk usage above 85%"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.boot_disk_usage_percent[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 85
      duration        = "0s"

      # boot_disk_usage_percent is a DELTA/DISTRIBUTION logs metric. ALIGN_MEAN
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
    time_sleep.wait_boot_disk_usage_metric,
  ]
}

# Alert policy - application logs have stopped arriving.
#
# This is the one condition in this file that does not depend on the thing it
# is watching still working. Every other policy here is a threshold on a
# log-based metric, and a threshold on a metric receiving no data does not fire
# — it goes quiet. So when the full boot disk broke Docker's log writing on
# 2026-09-01, every log-based metric stopped receiving points and the entire
# alerting stack went silent for 19 days rather than paging (issue #1826). The
# monitoring intended to catch disk exhaustion was disabled by the disk
# exhaustion.
#
# condition_absent inverts that: no data IS the alert. It fires for a full
# disk, a crashed scheduler, a wedged container, a broken logging agent, or
# anything else that stops the 15-minute check_resource_usage tick — without
# needing to enumerate them.
#
# 3600s (4 missed ticks) rather than something tighter: a rolling MIG update,
# an instance recreation, or a slow GTFS refresh can each stall a tick or two,
# and this policy's whole value is that it is trusted enough not to be muted.
resource "google_monitoring_alert_policy" "application_logs_absent" {
  count = var.environment == "production" ? 1 : 0

  display_name = "Application Logs Absent"
  combiner     = "OR"

  conditions {
    display_name = "No application logs for 1 hour"

    condition_absent {
      # Watches the data-disk heartbeat specifically because it is emitted by
      # the same 15-minute task as every other resource metric, and it predates
      # this policy — so the signal is already known-good in production. Any of
      # them going absent means the same thing; one absence policy is enough,
      # and more would just page in duplicate for one outage.
      filter   = "resource.type = \"gce_instance\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.data_disk_usage_percent[0].name}\""
      duration = "3600s"

      # The cross-series reduction is load-bearing here in a way it is not for
      # the threshold policies above. An absence condition evaluates per time
      # series, and these series are keyed by instance_id — so every MIG
      # instance recreation would strand a series that correctly never reports
      # again, and this policy would page about a machine that no longer
      # exists. Reducing with no group_by collapses every instance into one
      # series, which goes absent only when *nothing* is reporting. That is
      # also the question actually being asked: not "is instance X quiet" but
      # "are we receiving application logs at all".
      aggregations {
        alignment_period     = "1800s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    # 7 days, set explicitly because it is the longest Cloud Monitoring allows
    # and because leaving the field unset would *not* mean "never": Monitoring
    # applies the same 7-day default to an incident whose condition has stopped
    # receiving data, which is every incident this policy can open. So an
    # outage on the scale of the 19-day one that prompted this would close
    # itself at day 7 with the logs still absent.
    #
    # The other policies here use 1800s, which suits a value that recovers. For
    # absence it would mean forgetting an ongoing outage about as fast as it
    # was noticed.
    auto_close = "604800s"

    # The 7-day ceiling is not configurable, so the defence against a long
    # outage is re-notification rather than a longer incident: a daily reminder
    # while it stays open. Frequent enough that an ongoing blackout cannot be
    # quietly forgotten, rare enough that nobody mutes the policy — which for
    # the one alert here that survives its own subject failing would be the
    # worst outcome available.
    notification_channel_strategy {
      notification_channel_names = [
        google_monitoring_notification_channel.email[0].name,
      ]
      renotify_interval = "86400s"
    }
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
