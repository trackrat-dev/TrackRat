# Note: provider configuration and variables are in dashboards.tf

# --- Uptime Checks for External Dependencies ---

resource "google_monitoring_uptime_check_config" "nj_transit_api" {
  project      = var.project_id
  display_name = "NJ Transit API Uptime Check"

  http_check {
    path         = var.nj_transit_api_path
    port         = 443
    use_ssl      = true
    validate_ssl = true
    # headers = { # Example if API key needed
    #   "X-Api-Key" = var.nj_transit_api_key
    # }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host = var.nj_transit_api_host
    }
  }

  period           = "300s" # 5 minutes
  timeout          = "10s"
  selected_regions = var.uptime_check_regions
}

resource "google_monitoring_uptime_check_config" "amtrak_api" {
  project      = var.project_id
  display_name = "Amtrak API Uptime Check"

  http_check {
    path         = var.amtrak_api_path
    port         = 443
    use_ssl      = true
    validate_ssl = true
    # headers = { ... } # If auth needed
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host = var.amtrak_api_host
    }
  }

  period           = "300s"
  timeout          = "10s"
  selected_regions = var.uptime_check_regions
}

# --- Alert Policies for Uptime Check Failures ---

resource "google_monitoring_alert_policy" "nj_transit_api_down" {
  project      = var.project_id
  display_name = "Critical - NJ Transit API Unreachable"
  combiner     = "OR"

  conditions {
    display_name = "NJ Transit API Uptime Check Failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\" metric.label.check_id=\"${google_monitoring_uptime_check_config.nj_transit_api.uptime_check_id}\""
      comparison      = "COMPARISON_EQ" # Alert if check_passed is false (0)
      threshold_value = 0               # 0 means false (check failed)
      duration        = "600s"          # Alert if failing for 10 minutes (2 consecutive failed checks)
      trigger {
        count = 1 # Alert if condition met once (i.e., 0 passed checks for 10 mins)
      }
    }
  }

  alert_strategy {
    auto_close = "7200s" # Auto-close after 2 hours if resolved
  }

  notification_channels = var.critical_alert_channel_ids
  documentation {
    content   = "The NJ Transit API is failing its uptime check. This may impact data collection for NJ Transit services. Check the uptime check details in Google Cloud Monitoring and the status of the NJ Transit API."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity"   = "critical"
    "tier"       = "dependency"
    "dependency" = "nj_transit_api"
  }
}

resource "google_monitoring_alert_policy" "amtrak_api_down" {
  project      = var.project_id
  display_name = "Critical - Amtrak API Unreachable"
  combiner     = "OR"

  conditions {
    display_name = "Amtrak API Uptime Check Failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\" metric.label.check_id=\"${google_monitoring_uptime_check_config.amtrak_api.uptime_check_id}\""
      comparison      = "COMPARISON_EQ"
      threshold_value = 0
      duration        = "600s"
      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "7200s"
  }

  notification_channels = var.critical_alert_channel_ids
  documentation {
    content   = "The Amtrak API is failing its uptime check. This may impact data collection for Amtrak services. Check the uptime check details in Google Cloud Monitoring and the status of the Amtrak API."
    mime_type = "text/markdown"
  }
  user_labels = {
    "severity"   = "critical"
    "tier"       = "dependency"
    "dependency" = "amtrak_api"
  }
}

# --- Quota Monitoring for External APIs (Conceptual) ---
# Monitoring API quotas for external dependencies like NJ Transit and Amtrak is crucial
# to prevent service disruptions due to exceeding rate limits or usage tiers.
#
# Implementation strategies typically involve:
# 1. API-Provided Quota Information:
#    - Some APIs expose current quota usage or limits through response headers (e.g., X-RateLimit-Remaining)
#      or dedicated API endpoints.
#    - The application would need to parse this information.
#
# 2. Custom Metrics:
#    - If quota information is available in API responses, the application should publish these
#      as custom metrics to Google Cloud Monitoring (e.g., using Prometheus client libraries).
#    - Metrics could include `quota_remaining_ratio` or `quota_usage_count`.
#
# 3. Alerting on Custom Metrics:
#    - Once quota metrics are in Cloud Monitoring, alert policies can be created (similar to other custom metrics)
#      to warn when usage approaches limits (e.g., remaining quota < 10%).
#
# 4. GCP Service Quotas:
#    - If these external APIs are accessed through a GCP intermediary service (like API Gateway, Apigee,
#      or even Cloud Functions acting as proxies), then standard GCP service quota monitoring
#      and alerting can be applied to that intermediary service.
#
# 5. Log-Based Metrics for Errors:
#    - Monitor application logs for specific error messages or status codes related to quota exhaustion
#      (e.g., HTTP 429 "Too Many Requests", HTTP 403 "Forbidden" with quota-related messages).
#      Log-based metrics can count these errors and trigger alerts.
#
# Since the method for obtaining quota information varies greatly between APIs and often
# requires application-side instrumentation, no specific Terraform resources are created here
# for direct external API quota monitoring. This would typically be an application-level concern
# to publish the relevant metrics first. Users should investigate the quota mechanisms of
# NJ Transit and Amtrak APIs and implement custom metric collection as needed.
