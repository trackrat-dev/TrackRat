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

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "DOUBLE"
    unit        = "%"
  }

  value_extractor = "EXTRACT(jsonPayload.usage_percent)"

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

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "DOUBLE"
    unit        = "GBy"
  }

  value_extractor = "EXTRACT(jsonPayload.size_gb)"

  depends_on = [google_project_service.apis["logging.googleapis.com"]]
}
