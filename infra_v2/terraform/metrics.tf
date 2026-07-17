# Log-Based Metrics for User Activity Tracking
#
# These metrics capture user engagement without requiring backend code changes.
# View in: GCP Console > Monitoring > Metrics Explorer
# Metric names: logging.googleapis.com/user/{metric_name}

locals {
  # Common metric configuration
  metrics_enabled = var.environment == "production"
}

# =============================================================================
# SEARCH METRIC
# Tracks: GET /api/v2/trains/departures
# Labels: origin (from_station), destination (to_station)
# =============================================================================
resource "google_logging_metric" "train_searches" {
  count = local.metrics_enabled ? 1 : 0

  name        = "train_searches"
  description = "Train departure searches by route"
  filter      = "jsonPayload.event=\"get_departures_request\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "origin"
      value_type  = "STRING"
      description = "Departure station code"
    }
    labels {
      key         = "destination"
      value_type  = "STRING"
      description = "Arrival station code"
    }
  }

  label_extractors = {
    "origin"      = "EXTRACT(jsonPayload.from_station)"
    "destination" = "EXTRACT(jsonPayload.to_station)"
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# TRAIN VIEW METRIC
# Tracks: GET /api/v2/trains/{train_id}
# Labels: train_id, origin (user's from_station if provided)
# =============================================================================
resource "google_logging_metric" "train_views" {
  count = local.metrics_enabled ? 1 : 0

  name        = "train_views"
  description = "Train detail page views"
  filter      = "jsonPayload.event=\"get_train_details_request\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "train_id"
      value_type  = "STRING"
      description = "Train ID"
    }
    labels {
      key         = "origin"
      value_type  = "STRING"
      description = "User origin station"
    }
  }

  label_extractors = {
    "train_id" = "EXTRACT(jsonPayload.train_id)"
    "origin"   = "EXTRACT(jsonPayload.from_station)"
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# FOLLOW METRIC
# Tracks: POST /api/v2/live-activities/register
# Labels: train_id, origin, destination
# =============================================================================
resource "google_logging_metric" "train_follows" {
  count = local.metrics_enabled ? 1 : 0

  name        = "train_follows"
  description = "Train follow actions (Live Activity registrations)"
  filter      = "jsonPayload.event=\"live_activity_registered\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "train_id"
      value_type  = "STRING"
      description = "Train number"
    }
    labels {
      key         = "origin"
      value_type  = "STRING"
      description = "Origin station code"
    }
    labels {
      key         = "destination"
      value_type  = "STRING"
      description = "Destination station code"
    }
  }

  label_extractors = {
    "train_id"    = "EXTRACT(jsonPayload.train_number)"
    "origin"      = "EXTRACT(jsonPayload.origin)"
    "destination" = "EXTRACT(jsonPayload.destination)"
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# PROVIDER AUTH FAILURE METRIC
# Tracks: upstream transit-provider auth failures in structured collector logs.
# Drives the "Provider API Auth Failure" alert in monitoring.tf.
# Scoped to this environment's GCE instances by hostname prefix so staging
# deployments don't trigger the production alert.
# =============================================================================
resource "google_logging_metric" "provider_auth_failures" {
  count = local.metrics_enabled ? 1 : 0

  name        = "provider_auth_failures"
  description = "Upstream transit-provider API auth failures (token invalid/expired)"
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cos_containers\"",
    "jsonPayload._HOSTNAME=~\"^trackrat-${var.environment}-\"",
    "jsonPayload.level=~\"(error|warning)\"",
    format("(%s)", join(" OR ", [
      "(jsonPayload.event=\"njt_api_http_error\" AND (jsonPayload.status_code=401 OR jsonPayload.status_code=403))",
      # NJT returns HTTP 200 with a null body when the API token is invalid (see
      # collectors/njt/client.py:345). The daily getStationSchedule call is the
      # canonical authenticated request and its non-list response surfaces here.
      "(jsonPayload.event=\"invalid_schedule_response_type\" AND jsonPayload.response_type=\"NoneType\")",
      "(jsonPayload.event=\"metra_feed_http_error\" AND (jsonPayload.status_code=401 OR jsonPayload.status_code=403))",
      "(jsonPayload.event=\"mbta_feed_http_error\" AND (jsonPayload.status_code=401 OR jsonPayload.status_code=403))",
      "(jsonPayload.event=~\"wmata_(predictions|jit)_api_failed\" AND (jsonPayload.status_code=401 OR jsonPayload.status_code=403 OR jsonPayload.error=~\"(401|403|Unauthorized|Forbidden)\"))",
      "(jsonPayload.event=\"task_execution_failed\" AND jsonPayload.task=~\"(metra|wmata|mbta)_collection\" AND jsonPayload.error=~\"(401|403|Unauthorized|Forbidden|Invalid token|authentication failed)\")",
    ])),
  ])

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "logger"
      value_type  = "STRING"
      description = "Module emitting the error"
    }
  }

  label_extractors = {
    "logger" = "EXTRACT(jsonPayload.logger)"
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# DATA DISK USAGE METRIC
# Tracks: persistent data disk utilization, logged periodically by
# SchedulerService.check_resource_usage (services/scheduler.py).
# Drives the "Data Disk Usage" alerts in monitoring.tf.
# =============================================================================
resource "google_logging_metric" "data_disk_usage_percent" {
  count = local.metrics_enabled ? 1 : 0

  name        = "data_disk_usage_percent"
  description = "Persistent data disk utilization percentage"
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cos_containers\"",
    "jsonPayload._HOSTNAME=~\"^trackrat-${var.environment}-\"",
    "jsonPayload.event=\"data_disk_usage_check\"",
  ])

  # Logs-based metrics only support counter (INT64) or DISTRIBUTION value types;
  # a scalar value_extractor requires DISTRIBUTION (GCP rejects it on any other
  # type). The alert reads this via ALIGN_DELTA + REDUCE_MEAN, which yields the
  # distribution's exact mean, so bucket boundaries don't affect the threshold.
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "%"
  }

  value_extractor = "EXTRACT(jsonPayload.usage_percent)"

  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 5
      offset             = 0
    }
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# DATABASE SIZE METRIC
# Tracks: Postgres database size in GB, for trend visibility (no alert —
# see the "Data Disk Usage" alerts in monitoring.tf for the actual paging
# signal, since the disk is what actually runs out of space).
# =============================================================================
resource "google_logging_metric" "database_size_gb" {
  count = local.metrics_enabled ? 1 : 0

  name        = "database_size_gb"
  description = "Postgres database size in GB"
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cos_containers\"",
    "jsonPayload._HOSTNAME=~\"^trackrat-${var.environment}-\"",
    "jsonPayload.event=\"database_size_check\"",
  ])

  # DISTRIBUTION (not GAUGE/DOUBLE): a value_extractor is only valid on a
  # distribution-typed logs metric. This metric has no alert (trend/dashboard
  # only); exponential buckets span a wide GB range as the database grows.
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "GBy"
  }

  value_extractor = "EXTRACT(jsonPayload.size_gb)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 20
      growth_factor      = 2
      scale              = 1
    }
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# TABLE VACUUM HEALTH METRIC
# Tracks: dead-tuple ratio (%) per high-churn table, logged periodically by
# SchedulerService.check_resource_usage (services/scheduler.py). Added after
# journey_stops (35M+ rows) went its entire lifetime with zero completed
# vacuum/analyze passes, causing a stale visibility map that surfaced as
# production query timeouts on route-history precompute (issue #1359) instead
# of as an alert. Drives the "Table Vacuum Health" alert in monitoring.tf.
# =============================================================================
resource "google_logging_metric" "table_dead_tuple_ratio_pct" {
  count = local.metrics_enabled ? 1 : 0

  name        = "table_dead_tuple_ratio_pct"
  description = "Dead tuple ratio (%) per monitored high-churn table"
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cos_containers\"",
    "jsonPayload._HOSTNAME=~\"^trackrat-${var.environment}-\"",
    "jsonPayload.event=\"table_vacuum_health_check\"",
  ])

  # DISTRIBUTION (not GAUGE/DOUBLE): a value_extractor is only valid on a
  # distribution-typed logs metric. The alert aggregates per table_name with
  # ALIGN_DELTA + REDUCE_MEAN, reading each distribution's exact mean.
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "%"

    labels {
      key        = "table_name"
      value_type = "STRING"
    }
  }

  value_extractor = "EXTRACT(jsonPayload.dead_tuple_ratio_pct)"
  label_extractors = {
    "table_name" = "EXTRACT(jsonPayload.table_name)"
  }

  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 5
      offset             = 0
    }
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}

# =============================================================================
# STOP-ORDER WARNING METRIC
# Tracks: NJT journey stop-ordering warnings logged by the collector's
# _resequence_stops path (collectors/njt/journey.py) — origin_station_not_first
# and stops_missing_scheduled_times. Both fired for #1530 (Newark Penn rendered
# before Secaucus) and went unnoticed until in-app user feedback. Drives the
# "NJT Stop-Order Warnings" alert in monitoring.tf so a sustained misordering
# spike pages before a rider reports it. An `event` label is extracted for
# diagnosis; the alert sums across both events (mirrors provider_auth_failures).
# =============================================================================
resource "google_logging_metric" "stop_order_warnings" {
  count = local.metrics_enabled ? 1 : 0

  name        = "stop_order_warnings"
  description = "NJT stop-ordering warnings (origin displaced / stops missing scheduled times)"
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cos_containers\"",
    "jsonPayload._HOSTNAME=~\"^trackrat-${var.environment}-\"",
    "jsonPayload.level=\"warning\"",
    "(jsonPayload.event=\"origin_station_not_first\" OR jsonPayload.event=\"stops_missing_scheduled_times\")",
  ])

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "event"
      value_type  = "STRING"
      description = "Which ordering warning fired"
    }
  }

  label_extractors = {
    "event" = "EXTRACT(jsonPayload.event)"
  }

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}
