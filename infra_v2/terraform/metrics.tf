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
# Tracks: upstream transit-provider responses whose body contains
# "Invalid token" (NJT, WMATA, MBTA, Metra all surface this on bad credentials).
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
    "jsonPayload.level=\"error\"",
    "jsonPayload.error=~\"Invalid token\"",
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
