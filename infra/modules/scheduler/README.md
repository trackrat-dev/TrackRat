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
| [google_cloud_run_v2_service.scheduler_service](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service) | resource |
| [google_cloud_run_v2_service_iam_member.scheduler_job_invoker](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service_iam_member) | resource |
| [google_cloud_scheduler_job.scheduler_job](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_scheduler_job) | resource |
| [google_project_iam_member.run_sa_cloudsql_client](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.run_sa_secret_accessor](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_service_account.cloud_run_sa](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |
| [google_service_account.scheduler_job_sa](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_container_image"></a> [container\_image](#input\_container\_image) | Docker image URL for the scheduler service | `string` | n/a | yes |
| <a name="input_container_port"></a> [container\_port](#input\_container\_port) | Port the container listens on | `number` | `8080` | no |
| <a name="input_cpu_limit"></a> [cpu\_limit](#input\_cpu\_limit) | CPU limit for the container | `string` | `"1"` | no |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | A map of environment variables for the container | `map(string)` | `{}` | no |
| <a name="input_labels"></a> [labels](#input\_labels) | A map of labels to apply to the service. | `map(string)` | `{}` | no |
| <a name="input_location"></a> [location](#input\_location) | The GCP region for Cloud Run services and Scheduler | `string` | n/a | yes |
| <a name="input_max_instances"></a> [max\_instances](#input\_max\_instances) | Maximum number of instances (must be 1 for this service) | `number` | `1` | no |
| <a name="input_memory_limit"></a> [memory\_limit](#input\_memory\_limit) | Memory limit for the container | `string` | `"512Mi"` | no |
| <a name="input_min_instances"></a> [min\_instances](#input\_min\_instances) | Minimum number of instances | `number` | `0` | no |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project ID | `string` | n/a | yes |
| <a name="input_request_timeout_seconds"></a> [request\_timeout\_seconds](#input\_request\_timeout\_seconds) | Request timeout in seconds (up to 3600 for Cloud Run v2, issue asks for 60 mins) | `number` | `3600` | no |
| <a name="input_scheduler_job_description"></a> [scheduler\_job\_description](#input\_scheduler\_job\_description) | Description for the Cloud Scheduler job | `string` | `"Triggers the TrackRat Scheduler service"` | no |
| <a name="input_scheduler_job_name"></a> [scheduler\_job\_name](#input\_scheduler\_job\_name) | Name for the Cloud Scheduler job | `string` | `"invoke-trackrat-scheduler"` | no |
| <a name="input_scheduler_job_service_account_email"></a> [scheduler\_job\_service\_account\_email](#input\_scheduler\_job\_service\_account\_email) | Service account email for the Cloud Scheduler job to invoke the Cloud Run service. If null, one is created. | `string` | `null` | no |
| <a name="input_scheduler_schedule"></a> [scheduler\_schedule](#input\_scheduler\_schedule) | Cron schedule for the job (e.g., '0 * * * *' for hourly) | `string` | n/a | yes |
| <a name="input_scheduler_service_account_email"></a> [scheduler\_service\_account\_email](#input\_scheduler\_service\_account\_email) | Service account email for the Cloud Run service. If null, one is created. | `string` | `null` | no |
| <a name="input_scheduler_timezone"></a> [scheduler\_timezone](#input\_scheduler\_timezone) | Timezone for the scheduler job | `string` | `"Etc/UTC"` | no |
| <a name="input_secret_environment_variables"></a> [secret\_environment\_variables](#input\_secret\_environment\_variables) | A map of environment variables to be sourced from Secret Manager. | `map(string)` | `{}` | no |
| <a name="input_service_name"></a> [service\_name](#input\_service\_name) | Name of the Scheduler Cloud Run service | `string` | `"trackrat-scheduler"` | no |
| <a name="input_vpc_connector_id"></a> [vpc\_connector\_id](#input\_vpc\_connector\_id) | ID of the VPC Access Connector. Null if not needed. | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_scheduler_cloud_run_service_account_email"></a> [scheduler\_cloud\_run\_service\_account\_email](#output\_scheduler\_cloud\_run\_service\_account\_email) | Email of the service account used by the Scheduler Cloud Run service |
| <a name="output_scheduler_cloud_run_service_name"></a> [scheduler\_cloud\_run\_service\_name](#output\_scheduler\_cloud\_run\_service\_name) | Name of the deployed Scheduler Cloud Run service |
| <a name="output_scheduler_cloud_run_service_url"></a> [scheduler\_cloud\_run\_service\_url](#output\_scheduler\_cloud\_run\_service\_url) | URL of the deployed Scheduler Cloud Run service |
| <a name="output_scheduler_job_name"></a> [scheduler\_job\_name](#output\_scheduler\_job\_name) | Name of the Cloud Scheduler job |
| <a name="output_scheduler_job_service_account_email"></a> [scheduler\_job\_service\_account\_email](#output\_scheduler\_job\_service\_account\_email) | Email of the service account used by the Cloud Scheduler job |
<!-- END_TF_DOCS -->