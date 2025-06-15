terraform {
  required_version = ">= 1.0"
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

variable "db_instance_name" {
  description = "The name of the Cloud SQL database instance (e.g., project:region:instance or just instance name if project is implicit)."
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

variable "nj_transit_api_host" {
  description = "Hostname for the NJ Transit API endpoint for uptime checks."
  type        = string
  default     = "api.njtransit.com" # Placeholder - update with actual host if different
}

variable "nj_transit_api_path" {
  description = "Path for the NJ Transit API health/status endpoint."
  type        = string
  default     = "/v2/status" # Placeholder - update with actual path
}

variable "amtrak_api_host" {
  description = "Hostname for the Amtrak API endpoint for uptime checks."
  type        = string
  default     = "api.amtrak.com" # Placeholder - update with actual host if different
}

variable "amtrak_api_path" {
  description = "Path for the Amtrak API health/status endpoint."
  type        = string
  default     = "/v2/status" # Placeholder - update with actual path
}

variable "uptime_check_regions" {
  description = "List of regions to run uptime checks from."
  type        = list(string)
  default     = ["USA_EAST_VIRGINIA", "USA_WEST_CALIFORNIA", "EUROPE_WEST_BELGIUM"]
}

// Placeholder variables for custom metric names.
// These should be updated with actual metric names once known from Google Cloud Monitoring.
variable "nj_transit_success_metric_name" {
  description = "Metric name for NJ Transit fetch successes."
  type        = string
  default     = "custom.googleapis.com/fastapi/nj_transit_fetch_success_total"
}

variable "nj_transit_failure_metric_name" {
  description = "Metric name for NJ Transit fetch failures."
  type        = string
  default     = "custom.googleapis.com/fastapi/nj_transit_fetch_failures_total"
}

variable "amtrak_success_metric_name" {
  description = "Metric name for Amtrak fetch successes."
  type        = string
  default     = "custom.googleapis.com/fastapi/amtrak_fetch_success_total"
}

variable "amtrak_failure_metric_name" {
  description = "Metric name for Amtrak fetch failures."
  type        = string
  default     = "custom.googleapis.com/fastapi/amtrak_fetch_failures_total"
}

variable "model_inference_time_metric_name" {
  description = "Metric name for model inference time (histogram)."
  type        = string
  default     = "custom.googleapis.com/fastapi/model_inference_time_seconds"
}

variable "trains_processed_metric_name" {
  description = "Metric name for total trains processed."
  type        = string
  default     = "custom.googleapis.com/fastapi/trains_processed_total"
}

variable "prediction_confidence_metric_name" {
  description = "Metric name for track prediction confidence (histogram)."
  type        = string
  default     = "custom.googleapis.com/fastapi/track_prediction_confidence_ratio"
}


variable "db_query_duration_metric_name" {
  description = "Metric name for database query duration (histogram)."
  type        = string
  default     = "custom.googleapis.com/fastapi/db_query_duration_seconds"
}


# --- Operations Dashboard ---
resource "google_monitoring_dashboard" "operations_dashboard" {
  project = var.project_id
  dashboard_json = jsonencode({
    "displayName" : "TrackCast - Operations Dashboard",
    "gridLayout" : {
      "widgets" : [
        // API Performance Widgets
        {
          "title" : "API Request Rate (Cloud Run)",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_RATE"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "timeshiftDuration" : "0s",
            "yAxis" : {
              "label" : "Requests/sec",
              "scale" : "LINEAR"
            }
          }
        },
        {
          "title" : "API Error Rate (5XX - Cloud Run)",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\" metric.label.response_code_class=\"5XX\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_RATE"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "timeshiftDuration" : "0s",
            "yAxis" : {
              "label" : "Errors/sec",
              "scale" : "LINEAR"
            }
          }
        },
        {
          "title" : "API P95 Latency (Cloud Run)",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_PERCENTILE_95"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "timeshiftDuration" : "0s",
            "yAxis" : {
              "label" : "Latency (ms)",
              "scale" : "LINEAR"
            }
          }
        },
        // System Resources Widgets (Cloud Run)
        {
          "title" : "Cloud Run CPU Utilization",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/container/cpu/utilization\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_MEAN"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "yAxis" : { "label" : "CPU Utilization", "scale" : "LINEAR" }
          }
        },
        {
          "title" : "Cloud Run Memory Utilization",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/container/memory/utilization\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_MEAN"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "yAxis" : { "label" : "Memory Utilization", "scale" : "LINEAR" }
          }
        },
        // Database Health Widgets
        {
          "title" : "Database CPU Utilization",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\" resource.type=\"cloudsql_database\" resource.label.database_id=\"${var.db_instance_name}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_MEAN"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "yAxis" : { "label" : "CPU Utilization", "scale" : "LINEAR" }
          }
        },
        {
          "title" : "Database Active Connections",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    # Assuming PostgreSQL. For MySQL, use /database/mysql/num_connections
                    "filter" : "metric.type=\"cloudsql.googleapis.com/database/postgresql/num_backends\" resource.type=\"cloudsql_database\" resource.label.database_id=\"${var.db_instance_name}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "60s",
                      "perSeriesAligner" : "ALIGN_MEAN" # or ALIGN_MAX
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "yAxis" : { "label" : "Active Connections", "scale" : "LINEAR" }
          }
        },
        // Data Collection Status Widgets (Scorecards)
        {
          "title" : "NJ Transit Data Collected (Rate)",
          "scorecard" : {
            "timeSeriesQuery" : {
              "timeSeriesFilter" : {
                "filter" : "metric.type=\"${var.nj_transit_success_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                "aggregation" : {
                  "alignmentPeriod" : "60s", # Rate over 1 minute
                  "perSeriesAligner" : "ALIGN_RATE"
                }
              }
            },
            "thresholds" : [] # Optional: Add thresholds for visual cues
          }
        },
        {
          "title" : "Amtrak Data Collected (Rate)",
          "scorecard" : {
            "timeSeriesQuery" : {
              "timeSeriesFilter" : {
                "filter" : "metric.type=\"${var.amtrak_success_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                "aggregation" : {
                  "alignmentPeriod" : "60s",
                  "perSeriesAligner" : "ALIGN_RATE"
                }
              }
            },
            "thresholds" : []
          }
        }
      ]
    }
  })
}

# --- Business Dashboard ---
resource "google_monitoring_dashboard" "business_dashboard" {
  project = var.project_id
  dashboard_json = jsonencode({
    "displayName" : "TrackCast - Business KPIs Dashboard",
    "gridLayout" : {
      "widgets" : [
        // Prediction Accuracy Trends (Placeholder)
        /*
        {
          "title": "Model Prediction Accuracy (PMA)",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"${var.model_prediction_accuracy_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                    "aggregation": {
                      "alignmentPeriod": "3600s", // Hourly average
                      "perSeriesAligner": "ALIGN_MEAN",
                       "crossSeriesReducer": "REDUCE_MEAN", // If metric is per-station
                       "groupByFields": ["metric.label.station"]
                    }
                  }
                },
                "plotType": "LINE",
                "legendTemplate": "${metric.label.station}"
              }
            ],
            "yAxis": { "label": "Accuracy", "scale": "LINEAR" }
          },
          "description": "Note: This metric (model_prediction_accuracy) is currently a TODO in the application code and needs to be fully implemented for this chart to work."
        },
        */
        // Data Freshness Widgets (Scorecards showing time since last success)
        // This is tricky without a direct "last success timestamp" metric.
        // We can approximate by checking if there were any successes in the last N minutes.
        // A true "time since last event" is better done with custom metrics or log-based metrics.
        // Placeholder: Count of successful fetches in the last 5 minutes.
        {
          "title" : "NJ Transit Data - Recent Successes (Count in last 5min)",
          "scorecard" : {
            "timeSeriesQuery" : {
              "timeSeriesQuery" : {
                "query" : "fetch cloud_run_revision::custom.googleapis.com/fastapi/nj_transit_fetch_success_total | metric ::cloud_run_revision | filter resource.service_name == '${var.cloud_run_service_name}' | align delta(5m) | every 60s | group_by [], sum(val())"
              }
            },
            "thresholds" : [
              { "value" : 0.5, "color" : "RED", "direction" : "BELOW" } // Alert if less than 1 success in 5 mins
            ]
          }
        },
        {
          "title" : "Amtrak Data - Recent Successes (Count in last 5min)",
          "scorecard" : {
            "timeSeriesQuery" : {
              "timeSeriesQuery" : {
                "query" : "fetch cloud_run_revision::custom.googleapis.com/fastapi/amtrak_fetch_success_total | metric ::cloud_run_revision | filter resource.service_name == '${var.cloud_run_service_name}' | align delta(5m) | every 60s | group_by [], sum(val())"
              }
            },
            "thresholds" : [
              { "value" : 0.5, "color" : "RED", "direction" : "BELOW" }
            ]
          }
        },
        // Trains Processed Per Hour
        {
          "title" : "Trains Processed Per Hour",
          "xyChart" : {
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"${var.trains_processed_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "3600s", // 1 hour
                      "perSeriesAligner" : "ALIGN_RATE"
                    }
                  }
                },
                "plotType" : "LINE"
              }
            ],
            "yAxis" : { "label" : "Trains/hour", "scale" : "LINEAR" }
          }
        },
        // Track Prediction Confidence Distribution
        {
          "title" : "Track Prediction Confidence Distribution",
          "xyChart" : { // Using xyChart to display a distribution (histogram)
            "chartOptions" : {
              "mode" : "COLOR" // COLOR mode is typical for heatmaps/histograms if data is bucketized
              // If it's a distribution metric type, GCP Monitoring handles it.
            },
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"${var.prediction_confidence_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                    // Aggregation for distribution/histogram depends on how the metric is emitted.
                    // If it's a Prometheus histogram, it will have _bucket, _sum, _count.
                    // For a DISTRIBUTION metric type in Cloud Monitoring:
                    "aggregation" : {
                      "alignmentPeriod" : "3600s",          // Aggregate over 1 hour
                      "perSeriesAligner" : "ALIGN_DELTA",   // Use delta for counters if it's a counter-based histogram
                      "crossSeriesReducer" : "REDUCE_SUM",  // Sum counts from all instances
                      "groupByFields" : ["metric.label.le"] // If it's a prometheus histogram with 'le' label
                    }
                  },
                  "outputFullQueryText" : true // Useful for debugging the query
                },
                "plotType" : "HEATMAP" # Or STACKED_BAR if buckets are well-defined and few
                # "targetAxis": "Y1" # Ensure Y1 is configured if using that
              }
            ],
            "yAxis" : {
              "label" : "Count", # Or "Density"
              "scale" : "LINEAR"
            },
            "xAxis" : {
              "label" : "Confidence Score",
              "scale" : "LINEAR"
            }
            # "description": "Distribution of confidence scores for track predictions. This widget assumes the metric '${var.prediction_confidence_metric_name}' is a DISTRIBUTION type or a Prometheus histogram."
          }
        }
      ]
    }
  })
}

# --- Troubleshooting Dashboard ---
resource "google_monitoring_dashboard" "troubleshooting_dashboard" {
  project = var.project_id
  dashboard_json = jsonencode({
    "displayName" : "TrackCast - Troubleshooting Dashboard",
    "gridLayout" : {
      "widgets" : [
        // API Error Breakdown
        {
          "title" : "API Request Count by Response Code",
          "xyChart" : { // Using xyChart often more flexible for breakdowns than Pie
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\" resource.labels.location=\"${var.cloud_run_location}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "300s", // 5 minutes
                      "perSeriesAligner" : "ALIGN_RATE",
                      "crossSeriesReducer" : "REDUCE_SUM",
                      "groupByFields" : ["metric.label.response_code", "metric.label.response_code_class"]
                    }
                  }
                },
                "plotType" : "STACKED_BAR", // Or LINE
                "legendTemplate" : "$${metric.label.response_code_class} - $${metric.label.response_code}"
              }
            ],
            "timeshiftDuration" : "0s",
            "yAxis" : { "label" : "Request rate", "scale" : "LINEAR" }
          }
        },
        // Slow DB Queries (Placeholder)
        // Actual slow query logs are best viewed in Cloud SQL Insights.
        // This widget shows the distribution of all query latencies.
        {
          "title" : "DB Query Duration Distribution (All Types)",
          "xyChart" : {
            "chartOptions" : { "mode" : "COLOR" },
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"${var.db_query_duration_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                    "aggregation" : { // Aggregation for distribution/histogram
                      "alignmentPeriod" : "300s",
                      "perSeriesAligner" : "ALIGN_DELTA",
                      "crossSeriesReducer" : "REDUCE_SUM",
                      "groupByFields" : ["metric.label.le"] // Assuming 'le' for Prometheus histogram
                    }
                  }
                },
                "plotType" : "HEATMAP"
              }
            ],
            "yAxis" : { "label" : "Count", "scale" : "LINEAR" },
            "xAxis" : { "label" : "Query Duration (seconds)", "scale" : "LINEAR" },
            "description" : "Distribution of DB query durations. For specific slow queries, use Cloud SQL Insights."
          }
        },
        // Model Inference Times
        {
          "title" : "Model Inference Time Distribution",
          "xyChart" : {
            "chartOptions" : { "mode" : "COLOR" },
            "dataSets" : [
              {
                "timeSeriesQuery" : {
                  "timeSeriesFilter" : {
                    "filter" : "metric.type=\"${var.model_inference_time_metric_name}\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.cloud_run_service_name}\"",
                    "aggregation" : {
                      "alignmentPeriod" : "300s",
                      "perSeriesAligner" : "ALIGN_DELTA",
                      "crossSeriesReducer" : "REDUCE_SUM",
                      "groupByFields" : ["metric.label.le", "metric.label.station"] // Group by 'le' for histogram and 'station'
                    }
                  },
                  "outputFullQueryText" : true
                },
                "plotType" : "HEATMAP",
                "legendTemplate" : "$${metric.label.station}"
              }
            ],
            "yAxis" : { "label" : "Count", "scale" : "LINEAR" },
            "xAxis" : { "label" : "Inference Time (seconds)", "scale" : "LINEAR" }
          }
        },
        // Dependency Health - API Success Rates
        {
          "title" : "NJ Transit API Success Rate (5min avg)",
          "gaugeChart" : { # Using Gauge for a single percentage value
            "dataSets" : [{
              "timeSeriesQuery" : {
                "timeSeriesQuery" : { # Using MQL for ratio
                  "query" : <<-EOT
                    fetch cloud_run_revision
                    | {
                        metric '${var.nj_transit_success_metric_name}'
                        | align rate(5m)
                        | group_by [], total_success = sum(val());
                        metric '${var.nj_transit_failure_metric_name}'
                        | align rate(5m)
                        | group_by [], total_failure = sum(val())
                      }
                    | ratio (total_success / (total_success + total_failure))
                    | default 1 # Avoid no data if no failures
                  EOT
                }
              }
            }],
            # Min/Max for gauge are 0 to 1 (representing 0% to 100%)
            "lowerBound" : 0,
            "upperBound" : 1
          }
        },
        {
          "title" : "Amtrak API Success Rate (5min avg)",
          "gaugeChart" : {
            "dataSets" : [{
              "timeSeriesQuery" : {
                "timeSeriesQuery" : {
                  "query" : <<-EOT
                    fetch cloud_run_revision
                    | {
                        metric '${var.amtrak_success_metric_name}'
                        | align rate(5m)
                        | group_by [], total_success = sum(val());
                        metric '${var.amtrak_failure_metric_name}'
                        | align rate(5m)
                        | group_by [], total_failure = sum(val())
                      }
                    | ratio (total_success / (total_success + total_failure))
                    | default 1 # Avoid no data if no failures
                  EOT
                }
              }
            }],
            "lowerBound" : 0,
            "upperBound" : 1
          }
        }
      ]
    }
  })
}
