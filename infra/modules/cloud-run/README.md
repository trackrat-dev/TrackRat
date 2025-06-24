<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 5.45.2 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_cloud_run_domain_mapping.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_domain_mapping) | resource |
| [google_cloud_run_v2_service.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service) | resource |
| [google_cloud_run_v2_service_iam_member.public_invoker](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service_iam_member) | resource |
| [google_project_iam_member.artifact_registry_reader](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.cloud_trace_agent](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.cloudsql_client](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.monitoring_metric_writer](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.secret_accessor](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_service_account.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_annotations"></a> [annotations](#input\_annotations) | A map of annotations to apply to the service. | `map(string)` | `{}` | no |
| <a name="input_concurrency"></a> [concurrency](#input\_concurrency) | Number of concurrent requests per instance | `number` | `80` | no |
| <a name="input_container_image"></a> [container\_image](#input\_container\_image) | Docker image URL for the service | `string` | n/a | yes |
| <a name="input_container_port"></a> [container\_port](#input\_container\_port) | Port the container listens on | `number` | `8080` | no |
| <a name="input_cpu_limit"></a> [cpu\_limit](#input\_cpu\_limit) | CPU limit for the container (e.g., '1', '2') | `string` | `"1"` | no |
| <a name="input_custom_domain_name"></a> [custom\_domain\_name](#input\_custom\_domain\_name) | The custom domain name (e.g., api.example.com) | `string` | `""` | no |
| <a name="input_enable_cloudsql_access"></a> [enable\_cloudsql\_access](#input\_enable\_cloudsql\_access) | Whether to grant Cloud SQL client permissions to the service account | `bool` | `false` | no |
| <a name="input_enable_custom_domain"></a> [enable\_custom\_domain](#input\_enable\_custom\_domain) | Set to true to enable custom domain mapping | `bool` | `false` | no |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | A map of environment variables for the container | `map(string)` | `{}` | no |
| <a name="input_labels"></a> [labels](#input\_labels) | A map of labels to apply to the service. | `map(string)` | `{}` | no |
| <a name="input_liveness_probe_path"></a> [liveness\_probe\_path](#input\_liveness\_probe\_path) | Path for the liveness probe. Disabled if null. | `string` | `"/health"` | no |
| <a name="input_liveness_probe_period_seconds"></a> [liveness\_probe\_period\_seconds](#input\_liveness\_probe\_period\_seconds) | Periodicity of liveness probe in seconds. | `number` | `30` | no |
| <a name="input_location"></a> [location](#input\_location) | The GCP region for Cloud Run services | `string` | n/a | yes |
| <a name="input_max_instances"></a> [max\_instances](#input\_max\_instances) | Maximum number of instances | `number` | `2` | no |
| <a name="input_memory_limit"></a> [memory\_limit](#input\_memory\_limit) | Memory limit for the container (e.g., '512Mi', '1Gi') | `string` | `"2Gi"` | no |
| <a name="input_min_instances"></a> [min\_instances](#input\_min\_instances) | Minimum number of instances | `number` | `0` | no |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project ID | `string` | n/a | yes |
| <a name="input_request_timeout_seconds"></a> [request\_timeout\_seconds](#input\_request\_timeout\_seconds) | Request timeout in seconds | `number` | `60` | no |
| <a name="input_secret_environment_variables"></a> [secret\_environment\_variables](#input\_secret\_environment\_variables) | A map of environment variables to be sourced from Secret Manager. Key is the env var name, value is the secret name:version. | `map(string)` | `{}` | no |
| <a name="input_service_account_email"></a> [service\_account\_email](#input\_service\_account\_email) | Email of the service account to run the service as. If null, a new one will be created. | `string` | `null` | no |
| <a name="input_service_name"></a> [service\_name](#input\_service\_name) | Name of the Cloud Run service | `string` | n/a | yes |
| <a name="input_startup_probe_failure_threshold"></a> [startup\_probe\_failure\_threshold](#input\_startup\_probe\_failure\_threshold) | Failure threshold for startup probe | `number` | `60` | no |
| <a name="input_startup_probe_initial_delay_seconds"></a> [startup\_probe\_initial\_delay\_seconds](#input\_startup\_probe\_initial\_delay\_seconds) | Initial delay for startup probe in seconds | `number` | `0` | no |
| <a name="input_startup_probe_path"></a> [startup\_probe\_path](#input\_startup\_probe\_path) | Path for the startup probe (e.g., /healthz). Disabled if null. | `string` | `"/health"` | no |
| <a name="input_startup_probe_period_seconds"></a> [startup\_probe\_period\_seconds](#input\_startup\_probe\_period\_seconds) | Period for startup probe in seconds | `number` | `10` | no |
| <a name="input_startup_probe_timeout_seconds"></a> [startup\_probe\_timeout\_seconds](#input\_startup\_probe\_timeout\_seconds) | Timeout for startup probe in seconds | `number` | `5` | no |
| <a name="input_vpc_connector_id"></a> [vpc\_connector\_id](#input\_vpc\_connector\_id) | ID of the VPC Access Connector (self\_link) for private IP access to Cloud SQL. Null if not needed. | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_custom_domain_mapping_status"></a> [custom\_domain\_mapping\_status](#output\_custom\_domain\_mapping\_status) | Status of the custom domain mapping. Includes resource records to be created in DNS. |
| <a name="output_custom_domain_name"></a> [custom\_domain\_name](#output\_custom\_domain\_name) | The configured custom domain name. |
| <a name="output_service_account_email"></a> [service\_account\_email](#output\_service\_account\_email) | Email of the service account used by the Cloud Run service |
| <a name="output_service_name"></a> [service\_name](#output\_service\_name) | Name of the deployed Cloud Run service |
| <a name="output_service_revision"></a> [service\_revision](#output\_service\_revision) | Current revision of the Cloud Run service |
| <a name="output_service_url"></a> [service\_url](#output\_service\_url) | URL of the deployed Cloud Run service |
<!-- END_TF_DOCS -->