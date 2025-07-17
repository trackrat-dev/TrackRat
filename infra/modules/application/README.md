<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 4.20.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 6.44.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_monitoring_alert_policy.amtrak_api_down](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.api_down_request_count](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.api_high_error_rate](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.api_slow_response_p95](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.nj_transit_api_down](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.no_amtrak_data_collection](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.no_nj_transit_data_collection](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_dashboard.business_dashboard](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_dashboard) | resource |
| [google_monitoring_dashboard.executive_dashboard](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_dashboard) | resource |
| [google_monitoring_dashboard.operations_dashboard](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_dashboard) | resource |
| [google_monitoring_dashboard.troubleshooting_dashboard](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_dashboard) | resource |
| [google_monitoring_uptime_check_config.amtrak_api](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_uptime_check_config) | resource |
| [google_monitoring_uptime_check_config.nj_transit_api](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_uptime_check_config) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_amtrak_api_host"></a> [amtrak\_api\_host](#input\_amtrak\_api\_host) | Hostname for the Amtrak API endpoint for uptime checks. | `string` | `"api.amtrak.com"` | no |
| <a name="input_amtrak_api_path"></a> [amtrak\_api\_path](#input\_amtrak\_api\_path) | Path for the Amtrak API health/status endpoint. | `string` | `"/v2/status"` | no |
| <a name="input_amtrak_failure_metric_name"></a> [amtrak\_failure\_metric\_name](#input\_amtrak\_failure\_metric\_name) | Metric name for Amtrak fetch failures. | `string` | `"custom.googleapis.com/fastapi/amtrak_fetch_failures_total"` | no |
| <a name="input_amtrak_success_metric_name"></a> [amtrak\_success\_metric\_name](#input\_amtrak\_success\_metric\_name) | Metric name for Amtrak fetch successes. | `string` | `"custom.googleapis.com/fastapi/amtrak_fetch_success_total"` | no |
| <a name="input_api_error_rate_threshold"></a> [api\_error\_rate\_threshold](#input\_api\_error\_rate\_threshold) | Error rate threshold (0.0 to 1.0) for API error rate alert. | `number` | `0.05` | no |
| <a name="input_api_latency_p95_threshold_seconds"></a> [api\_latency\_p95\_threshold\_seconds](#input\_api\_latency\_p95\_threshold\_seconds) | P95 latency threshold in seconds for API response time alert. | `number` | `2` | no |
| <a name="input_cloud_run_location"></a> [cloud\_run\_location](#input\_cloud\_run\_location) | The location of the Cloud Run service. | `string` | n/a | yes |
| <a name="input_cloud_run_service_name"></a> [cloud\_run\_service\_name](#input\_cloud\_run\_service\_name) | The name of the Cloud Run service. | `string` | n/a | yes |
| <a name="input_critical_alert_channel_ids"></a> [critical\_alert\_channel\_ids](#input\_critical\_alert\_channel\_ids) | List of notification channel IDs for critical alerts. | `list(string)` | n/a | yes |
| <a name="input_db_instance_name"></a> [db\_instance\_name](#input\_db\_instance\_name) | The name of the Cloud SQL database instance (e.g., project:region:instance or just instance name if project is implicit). | `string` | n/a | yes |
| <a name="input_db_query_duration_metric_name"></a> [db\_query\_duration\_metric\_name](#input\_db\_query\_duration\_metric\_name) | Metric name for database query duration (histogram). | `string` | `"custom.googleapis.com/fastapi/db_query_duration_seconds"` | no |
| <a name="input_model_inference_time_metric_name"></a> [model\_inference\_time\_metric\_name](#input\_model\_inference\_time\_metric\_name) | Metric name for model inference time (histogram). | `string` | `"custom.googleapis.com/fastapi/model_inference_time_seconds"` | no |
| <a name="input_nj_transit_api_host"></a> [nj\_transit\_api\_host](#input\_nj\_transit\_api\_host) | Hostname for the NJ Transit API endpoint for uptime checks. | `string` | `"api.njtransit.com"` | no |
| <a name="input_nj_transit_api_path"></a> [nj\_transit\_api\_path](#input\_nj\_transit\_api\_path) | Path for the NJ Transit API health/status endpoint. | `string` | `"/v2/status"` | no |
| <a name="input_nj_transit_failure_metric_name"></a> [nj\_transit\_failure\_metric\_name](#input\_nj\_transit\_failure\_metric\_name) | Metric name for NJ Transit fetch failures. | `string` | `"custom.googleapis.com/fastapi/nj_transit_fetch_failures_total"` | no |
| <a name="input_nj_transit_success_metric_name"></a> [nj\_transit\_success\_metric\_name](#input\_nj\_transit\_success\_metric\_name) | Metric name for NJ Transit fetch successes. | `string` | `"custom.googleapis.com/fastapi/nj_transit_fetch_success_total"` | no |
| <a name="input_prediction_confidence_metric_name"></a> [prediction\_confidence\_metric\_name](#input\_prediction\_confidence\_metric\_name) | Metric name for track prediction confidence (histogram). | `string` | `"custom.googleapis.com/fastapi/track_prediction_confidence_ratio"` | no |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the Google Cloud project. | `string` | n/a | yes |
| <a name="input_trains_processed_metric_name"></a> [trains\_processed\_metric\_name](#input\_trains\_processed\_metric\_name) | Metric name for total trains processed. | `string` | `"custom.googleapis.com/fastapi/trains_processed_total"` | no |
| <a name="input_uptime_check_regions"></a> [uptime\_check\_regions](#input\_uptime\_check\_regions) | List of regions to run uptime checks from. | `list(string)` | <pre>[<br/>  "USA_EAST_VIRGINIA",<br/>  "USA_WEST_CALIFORNIA",<br/>  "EUROPE_WEST_BELGIUM"<br/>]</pre> | no |
| <a name="input_warning_alert_channel_ids"></a> [warning\_alert\_channel\_ids](#input\_warning\_alert\_channel\_ids) | List of notification channel IDs for warning alerts. | `list(string)` | n/a | yes |

## Outputs

No outputs.
<!-- END_TF_DOCS -->