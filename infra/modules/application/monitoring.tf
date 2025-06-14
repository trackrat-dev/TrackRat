terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.20.0" # Specify a version constraint
    }
  }
}

variable "project_id" {
  description = "The ID of the Google Cloud project."
  type        = string
}

variable "cloud_run_service_name" {
  description = "The name of the Cloud Run service."
  type        = string
}

variable "cloud_run_location" {
  description = "The location of the Cloud Run service."
  type        = string
}

variable "critical_alert_channel_ids" {
  description = "List of notification channel IDs for critical alerts."
  type        = list(string)
}

variable "warning_alert_channel_ids" {
  description = "List of notification channel IDs for warning alerts."
  type        = list(string)
}

variable "api_error_rate_threshold" {
  description = "Error rate threshold (0.0 to 1.0) for API error rate alert."
  type        = number
  default     = 0.05
}

variable "api_latency_p95_threshold_seconds" {
  description = "P95 latency threshold in seconds for API response time alert."
  type        = number
  default     = 2.0
}

# --- Application Monitoring Alerts ---

# Critical Alert - API Down (No requests or Uptime Check Failure)
# Option 1: Using request_count (simpler if any traffic is expected)
resource "google_monitoring_alert_policy" "api_down_request_count" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - API Down (No Requests)"
  combiner     = "OR"
  conditions {
    display_name = "No requests seen for > 5 minutes"
    condition_metric_absence {
      filter   = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\""
      duration = "300s" # 5 minutes
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
      trigger {
        count = 1 # Alert if the sum of requests is absent for 5 minutes
      }
    }
  }
  alert_strategy {
    auto_close = "3600s" # Auto-close after 1 hour
  }
  notification_channels = var.critical_alert_channel_ids
  documentation {
    content = "The Cloud Run service ${var.cloud_run_service_name} is not receiving any requests, or the request_count metric is not reporting. This could indicate the service is down or inaccessible."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "critical"
    "tier"     = "application"
  }
}

# TODO: Consider adding an Uptime Check based alert for more robust API down detection.
# resource "google_monitoring_uptime_check_config" "api_uptime_check" { ... }
# resource "google_monitoring_alert_policy" "api_down_uptime_check" { ... }

# Critical Alert - No Data Collection (NJ Transit)
resource "google_monitoring_alert_policy" "no_nj_transit_data_collection" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - No NJ Transit Data Collection"
  combiner     = "OR"
  conditions {
    display_name = "NJ Transit fetch success count has not increased for > 30 minutes"
    condition_threshold {
      # Assumes metric name: custom.googleapis.com/fastapi/nj_transit_fetch_success_total
      # Replace with actual metric name found in Google Cloud Monitoring
      filter          = "metric.type=\"custom.googleapis.com/fastapi/nj_transit_fetch_success_total\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\""
      duration        = "1800s" # 30 minutes
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      aggregations {
        alignment_period   = "1800s" # Aligned with duration for increase check
        per_series_aligner = "ALIGN_DELTA" # Checks the increase over the alignment period
      }
      trigger {
        count = 1 # Alert if increase is less than 1 over 30 mins
      }
    }
  }
  alert_strategy {
    auto_close = "7200s" # Auto-close after 2 hours
  }
  notification_channels = var.critical_alert_channel_ids
  documentation {
    content   = "The application has not successfully fetched data from NJ Transit API for over 30 minutes. This impacts data freshness and predictions."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "critical"
    "tier"     = "data_collection"
  }
}

# Critical Alert - No Data Collection (Amtrak)
resource "google_monitoring_alert_policy" "no_amtrak_data_collection" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - No Amtrak Data Collection"
  combiner     = "OR"
  conditions {
    display_name = "Amtrak fetch success count has not increased for > 30 minutes"
    condition_threshold {
      # Assumes metric name: custom.googleapis.com/fastapi/amtrak_fetch_success_total
      # Replace with actual metric name found in Google Cloud Monitoring
      filter          = "metric.type=\"custom.googleapis.com/fastapi/amtrak_fetch_success_total\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\""
      duration        = "1800s" # 30 minutes
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      aggregations {
        alignment_period   = "1800s"
        per_series_aligner = "ALIGN_DELTA"
      }
      trigger {
        count = 1
      }
    }
  }
  alert_strategy {
    auto_close = "7200s" # Auto-close after 2 hours
  }
  notification_channels = var.critical_alert_channel_ids
  documentation {
    content   = "The application has not successfully fetched data from Amtrak API for over 30 minutes. This impacts data freshness and predictions."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "critical"
    "tier"     = "data_collection"
  }
}

# Warning Alert - High API Error Rates
resource "google_monitoring_alert_policy" "api_high_error_rate" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - High API Error Rate (> ${var.api_error_rate_threshold * 100}%)"
  combiner     = "OR"
  conditions {
    display_name = "Server error rate > ${var.api_error_rate_threshold * 100}% for 5 minutes"
    condition_monitoring_query_language {
      query = <<-QUERY
        fetch cloud_run_revision
        | metric 'run.googleapis.com/request_count'
        | filter resource.service_name == '${var.cloud_run_service_name}' && resource.location == '${var.cloud_run_location}'
        | align rate(5m)
        | every 30s
        | {
        |   filter_5xx: metric response_code_class == '5XX'
        |   ;
        |   total:
        | }
        | ratio filter_5xx / total
        | condition val() > ${var.api_error_rate_threshold}
      QUERY
      duration = "300s" # 5 minutes
      trigger {
        count = 1
      }
    }
  }
  alert_strategy {
    auto_close = "3600s" # Auto-close after 1 hour
  }
  notification_channels = var.warning_alert_channel_ids
  documentation {
    content   = "The API error rate for ${var.cloud_run_service_name} has exceeded ${var.api_error_rate_threshold * 100}% over the last 5 minutes."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "warning"
    "tier"     = "application"
  }
}

# Warning Alert - Slow API Response Times (P95)
resource "google_monitoring_alert_policy" "api_slow_response_p95" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - Slow API Response P95 (> ${var.api_latency_p95_threshold_seconds}s)"
  combiner     = "OR"
  conditions {
    display_name = "P95 latency > ${var.api_latency_p95_threshold_seconds}s for 5 minutes"
    condition_threshold {
      # Assumes Prometheus metric name: custom.googleapis.com/fastapi/http_request_duration_seconds_bucket
      # Replace with actual metric name. This filter targets the P95 bucket.
      # The actual bucket and value depend on your Prometheus histogram configuration.
      # This is a simplified example; a more precise approach uses distribution_cut.
      filter          = "metric.type=\"custom.googleapis.com/fastapi/http_request_duration_seconds_bucket\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" metric.label.le=\"${var.api_latency_p95_threshold_seconds}\""
      duration        = "300s" # 5 minutes
      comparison      = "COMPARISON_GT" # This is conceptual for a bucket; better to use distribution percentile
      threshold_value = 0.95   # This is not how bucket comparison works.
                               # For histograms, you'd typically use a condition_monitoring_query_language with distribution functions.
                               # Example MQL:
                               # fetch cloud_run_revision
                               # | metric 'custom.googleapis.com/fastapi/http_request_duration_seconds'
                               # | filter resource.service_name == '${var.cloud_run_service_name}'
                               # | group_by [resource.location], .sum()
                               # | align rate(5m)
                               # | every 30s
                               # | group_by [], .percentile_true(95, sum)
                               # | condition val() > ${var.api_latency_p95_threshold_seconds}
      # This is a placeholder for demonstration.
      # A real implementation for Prometheus histograms would use MQL with percentile aggregators.
      # For now, this will likely not work as intended without MQL.
      # We will use a simplified filter that might not be accurate.
      # A more robust way is to use `condition_monitoring_query_language` for percentile.
      # Using a placeholder filter that will likely need adjustment:
      # filter          = "metric.type=\"custom.googleapis.com/fastapi/http_request_duration_seconds_summary_percentile\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" metric.label.quantile=\"0.95\""
      # comparison      = "COMPARISON_GT"
      # threshold_value = var.api_latency_p95_threshold_seconds

      # Using MQL for P95 latency from a distribution metric
      # This assumes 'custom.googleapis.com/fastapi/http_request_duration_seconds' is a DISTRIBUTION
      # If it's a HISTOGRAM (like _bucket, _sum, _count), the query would be more complex or need different setup.
      # For now, let's assume it's a distribution for simplicity in this example.
      # If it's a Prometheus histogram, the metric would be named ..._bucket, and we'd need to calculate percentile from buckets.
      # This is a common challenge. For now, we'll use a structure that anticipates a distribution metric.
      # If the actual metric is a histogram, this will need to be changed.
      # Correct MQL for distribution:
      # query = <<-QUERY
      #   fetch cloud_run_revision
      #   | metric 'custom.googleapis.com/fastapi/http_request_duration_seconds' # Assuming this is the distribution metric
      #   | filter resource.service_name == '${var.cloud_run_service_name}' && resource.location == '${var.cloud_run_location}'
      #   | group_by 5m, .percentile_value_at(95)
      #   | condition val() > ${var.api_latency_p95_threshold_seconds}
      # QUERY
      # For this placeholder, we'll use a simple threshold condition on a _sum or _mean if p95 is not directly available as a metric.
      # This is often the case with default Prometheus instrumentation if not explicitly configured for percentiles as separate metrics.
      # Let's assume a generic custom metric for average latency for now, as P95 from buckets is complex for a basic alert.
      # Or, use the standard run.googleapis.com/request_latencies if it provides P95.
      # Cloud Run provides `run.googleapis.com/request_latencies` which is a distribution.
      filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\""
      comparison = "COMPARISON_GT"
      threshold_value = var.api_latency_p95_threshold_seconds * 1000 #ms for request_latencies
      duration = "300s"
       aggregations {
        alignment_period = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
      trigger {
        count = 1
      }
    }
  }
  alert_strategy {
    auto_close = "3600s" # Auto-close after 1 hour
  }
  notification_channels = var.warning_alert_channel_ids
  documentation {
    content   = "The P95 API response time for ${var.cloud_run_service_name} has exceeded ${var.api_latency_p95_threshold_seconds} seconds over the last 5 minutes."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "warning"
    "tier"     = "application"
  }
}

# Warning Alert - Model Accuracy Drop (Placeholder)
/*
resource "google_monitoring_alert_policy" "model_accuracy_drop" {
  project      = var.project_id
  display_name = "${var.cloud_run_service_name} - Model Prediction Accuracy Drop"
  combiner     = "OR"
  conditions {
    display_name = "Model prediction accuracy has dropped significantly"
    condition_threshold {
      # Metric name: custom.googleapis.com/fastapi/model_prediction_accuracy (adjust if namespace is different)
      # This metric is currently a TODO in the application code.
      filter          = "metric.type=\"custom.googleapis.com/fastapi/model_prediction_accuracy\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" metric.label.station!=\"\"" # Ensure station label exists
      duration        = "900s" # 15 minutes
      comparison      = "COMPARISON_LT"
      # Threshold needs to be defined based on expected baseline.
      # Example: threshold_value = 0.6 for an expected 75% accuracy (0.75 * 0.8 = 0.6)
      # This requires a variable for expected_baseline_accuracy.
      threshold_value = 0.6 # Placeholder - replace with var.expected_accuracy_threshold
      aggregations {
        alignment_period   = "300s" # 5 minutes
        per_series_aligner = "ALIGN_MEAN" # Average accuracy over the alignment period
        cross_series_reducer = "REDUCE_MEAN" # Optional: Average across stations if alerting globally
        group_by_fields    = ["metric.label.station"]
      }
      trigger {
        count = 1
      }
    }
  }
  alert_strategy {
    auto_close = "7200s" # Auto-close after 2 hours
  }
  notification_channels = var.warning_alert_channel_ids
  documentation {
    content   = "Model prediction accuracy for ${var.cloud_run_service_name} has dropped below the acceptable threshold. This may indicate issues with the model, features, or data quality."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity" = "warning"
    "tier"     = "ml_model"
  }
}
*/

# --- Info Alerts ---
# Info alerts, such as daily summaries of processed trains, prediction confidence distributions,
# or capacity trending (e.g., DB connection pool growth over weeks), are typically better handled by:
# 1. Scheduled Reports: Using Google Cloud's reporting features or custom scripts to generate daily/weekly summaries.
# 2. Dashboards: Creating comprehensive monitoring dashboards that visualize these metrics over time.
# 3. Log-Based Metrics: For specific events or patterns, log-based metrics can be used to trigger lower-priority notifications or for dashboarding.
#
# High-frequency alert policies are generally not suitable for these types of informational "alerts."
# For example, a daily summary of TRAINS_PROCESSED_TOTAL would be a report, not an alert policy firing every few minutes.
# Capacity trending for DB_CONNECTION_POOL_UTILIZATION over weeks would be observed on a dashboard.
#
# No specific google_monitoring_alert_policy resources will be created for these info-level items in this file.
# They should be addressed through other monitoring and reporting strategies.
