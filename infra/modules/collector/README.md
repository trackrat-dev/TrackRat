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
| [google_cloud_run_v2_service.collector_service](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service) | resource |
| [google_cloud_run_v2_service_iam_member.pubsub_push_invoker](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service_iam_member) | resource |
| [google_project_iam_member.run_sa_cloudsql_client](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.run_sa_secret_accessor](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_pubsub_subscription.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription) | resource |
| [google_service_account.cloud_run_sa](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |
| [google_service_account.pubsub_push_sa](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |
| [google_service_account_iam_member.pubsub_sa_token_creator](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account_iam_member) | resource |
| [google_project.current](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ack_deadline_seconds"></a> [ack\_deadline\_seconds](#input\_ack\_deadline\_seconds) | The acknowledgment deadline for Pub/Sub messages. | `number` | `60` | no |
| <a name="input_collector_service_account_email"></a> [collector\_service\_account\_email](#input\_collector\_service\_account\_email) | Service account email for the Cloud Run service. If null, one is created. | `string` | `null` | no |
| <a name="input_concurrency_per_instance"></a> [concurrency\_per\_instance](#input\_concurrency\_per\_instance) | Number of concurrent messages/requests per instance | `number` | `10` | no |
| <a name="input_container_image"></a> [container\_image](#input\_container\_image) | Docker image URL for the collector service | `string` | n/a | yes |
| <a name="input_container_port"></a> [container\_port](#input\_container\_port) | Port the container listens on | `number` | `8080` | no |
| <a name="input_cpu_limit"></a> [cpu\_limit](#input\_cpu\_limit) | CPU limit for the container | `string` | `"1"` | no |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | A map of environment variables for the container | `map(string)` | `{}` | no |
| <a name="input_labels"></a> [labels](#input\_labels) | A map of labels to apply to the service. | `map(string)` | `{}` | no |
| <a name="input_location"></a> [location](#input\_location) | The GCP region for Cloud Run services | `string` | n/a | yes |
| <a name="input_max_instances"></a> [max\_instances](#input\_max\_instances) | Maximum number of instances for the collector service | `number` | `5` | no |
| <a name="input_memory_limit"></a> [memory\_limit](#input\_memory\_limit) | Memory limit for the container | `string` | `"2Gi"` | no |
| <a name="input_min_instances"></a> [min\_instances](#input\_min\_instances) | Minimum number of instances for the collector service | `number` | `0` | no |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project ID | `string` | n/a | yes |
| <a name="input_pubsub_subscription_name"></a> [pubsub\_subscription\_name](#input\_pubsub\_subscription\_name) | Name for the Pub/Sub subscription. | `string` | `""` | no |
| <a name="input_pubsub_topic_name"></a> [pubsub\_topic\_name](#input\_pubsub\_topic\_name) | Name of the existing Pub/Sub topic to subscribe to (just the name, not full path). | `string` | n/a | yes |
| <a name="input_request_timeout_seconds"></a> [request\_timeout\_seconds](#input\_request\_timeout\_seconds) | Request timeout in seconds for message processing | `number` | `300` | no |
| <a name="input_retry_policy"></a> [retry\_policy](#input\_retry\_policy) | Pub/Sub subscription retry policy. Object with 'minimum\_backoff' and 'maximum\_backoff'. | <pre>object({<br/>    minimum_backoff = optional(string, "10s")<br/>    maximum_backoff = optional(string, "600s")<br/>  })</pre> | <pre>{<br/>  "maximum_backoff": "600s",<br/>  "minimum_backoff": "10s"<br/>}</pre> | no |
| <a name="input_secret_environment_variables"></a> [secret\_environment\_variables](#input\_secret\_environment\_variables) | A map of environment variables to be sourced from Secret Manager. | `map(string)` | `{}` | no |
| <a name="input_service_name"></a> [service\_name](#input\_service\_name) | Name of the Collector Cloud Run service | `string` | `"trackrat-collector"` | no |
| <a name="input_vpc_connector_id"></a> [vpc\_connector\_id](#input\_vpc\_connector\_id) | ID of the VPC Access Connector. Null if not needed. | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_collector_cloud_run_service_account_email"></a> [collector\_cloud\_run\_service\_account\_email](#output\_collector\_cloud\_run\_service\_account\_email) | Email of the service account used by the Collector Cloud Run service |
| <a name="output_collector_cloud_run_service_name"></a> [collector\_cloud\_run\_service\_name](#output\_collector\_cloud\_run\_service\_name) | Name of the deployed Collector Cloud Run service |
| <a name="output_collector_cloud_run_service_url"></a> [collector\_cloud\_run\_service\_url](#output\_collector\_cloud\_run\_service\_url) | URL of the deployed Collector Cloud Run service |
| <a name="output_pubsub_push_service_account_email"></a> [pubsub\_push\_service\_account\_email](#output\_pubsub\_push\_service\_account\_email) | Email of the service account used by Pub/Sub to push messages to the Cloud Run service |
| <a name="output_pubsub_subscription_name"></a> [pubsub\_subscription\_name](#output\_pubsub\_subscription\_name) | Name of the Pub/Sub subscription created for the collector service |
| <a name="output_pubsub_subscription_topic"></a> [pubsub\_subscription\_topic](#output\_pubsub\_subscription\_topic) | Topic for the Pub/Sub subscription |
<!-- END_TF_DOCS -->