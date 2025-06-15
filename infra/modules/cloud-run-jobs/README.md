# Cloud Run Jobs Module

This Terraform module creates Google Cloud Run Jobs for executing scheduled batch operations. Cloud Run Jobs are ideal for running one-time or scheduled tasks that execute to completion and then terminate.

## Features

- Creates multiple Cloud Run Jobs from a single configuration
- Supports VPC connectivity for database access
- Handles secret management through Secret Manager
- Configurable resource limits and retry policies
- Proper IAM integration for Cloud Scheduler triggering

## Usage

```hcl
module "scheduled_jobs" {
  source = "./modules/cloud-run-jobs"

  project_id         = var.project_id
  location          = var.region
  job_name_prefix   = "trackrat-ops"
  container_image   = var.api_image_url
  service_account_email = google_service_account.jobs_sa.email
  vpc_connector_id  = module.vpc_connector.id

  # Global environment variables for all jobs
  environment_variables = {
    TRACKCAST_ENV = "development"
    MODEL_PATH   = "/app/models"
  }

  # Secret environment variables from Secret Manager
  secret_environment_variables = {
    DATABASE_URL = "database-secrets:latest"
    NJT_USERNAME = "njt-credentials:latest"
    NJT_PASSWORD = "njt-credentials:latest"
  }

  # Job configurations
  jobs = {
    data-collection = {
      command      = ["trackcast", "collect-data"]
      cpu_limit    = "1"
      memory_limit = "2Gi"
      max_retries  = 3
      task_timeout = "300s"
      environment_variables = {
        JOB_TYPE = "data_collection"
      }
    }
    
    feature-processing = {
      command      = ["trackcast", "process-features"]
      cpu_limit    = "2"
      memory_limit = "4Gi"
      max_retries  = 2
      task_timeout = "600s"
      environment_variables = {
        JOB_TYPE = "feature_processing"
      }
    }
    
    prediction-generation = {
      command      = ["trackcast", "generate-predictions"]
      cpu_limit    = "2"
      memory_limit = "4Gi"
      max_retries  = 2
      task_timeout = "600s"
      environment_variables = {
        JOB_TYPE = "prediction_generation"
      }
    }
  }

  labels = {
    environment = "development"
    component   = "scheduler"
  }
}
```

## Job Configuration

Each job in the `jobs` map supports the following configuration:

- `command` (required): List of strings defining the command to execute
- `args` (optional): List of command arguments
- `cpu_limit` (optional): CPU limit (default: "1")
- `memory_limit` (optional): Memory limit (default: "2Gi")
- `max_retries` (optional): Maximum retry attempts (default: 3)
- `task_timeout` (optional): Task timeout (default: "300s")
- `environment_variables` (optional): Job-specific environment variables

## Cloud Scheduler Integration

Use the job URIs output to configure Cloud Scheduler:

```hcl
resource "google_cloud_scheduler_job" "operations_jobs" {
  for_each = module.scheduled_jobs.job_uris

  name         = "schedule-${each.key}"
  description  = "Scheduled execution of ${each.key}"
  schedule     = var.job_schedules[each.key]
  time_zone    = "America/New_York"

  http_target {
    uri         = each.value
    http_method = "POST"
    
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
      audience             = each.value
    }
  }
}
```

## Advantages over HTTP API Endpoints

This Cloud Run Jobs approach offers several advantages over the previous HTTP endpoint approach:

1. **Resource Efficiency**: Jobs only consume resources when running
2. **Cost Optimization**: No minimum instances required (vs API service min_instances = 1)
3. **Better Isolation**: Each operation runs independently
4. **Improved Monitoring**: Separate execution tracking per job type
5. **Cleaner Architecture**: Direct CLI execution without HTTP wrapper

## IAM Requirements

The service account used for job execution needs the following permissions:

- `run.jobs.run` - To execute the jobs
- `secretmanager.versions.access` - To access secrets
- Database connection permissions (via VPC or Cloud SQL Auth Proxy)

## Monitoring and Logging

Cloud Run Jobs automatically provide:

- Execution logs in Cloud Logging
- Metrics in Cloud Monitoring
- Job execution history and status
- Resource usage tracking

## Resource Limits

Configure appropriate resource limits based on workload:

- **Data Collection**: Light workload, 1 CPU / 2Gi memory
- **Feature Processing**: Medium workload, 2 CPU / 4Gi memory  
- **Prediction Generation**: Heavy workload, 2-4 CPU / 4-8Gi memory

## Error Handling

Jobs will automatically retry based on `max_retries` configuration:

- Transient failures (network issues) are retried automatically
- Application errors (exit code != 0) respect retry configuration
- Task timeout failures will not be retried

## Migration from API Endpoints

When migrating from HTTP endpoints to Cloud Run Jobs:

1. Deploy this module alongside existing API endpoints
2. Update Cloud Scheduler to target job URIs instead of HTTP endpoints
3. Test job execution thoroughly
4. Remove API endpoints once jobs are working
5. Update API service to remove min_instances requirement
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
| [google_cloud_run_v2_job.operation_jobs](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_container_image"></a> [container\_image](#input\_container\_image) | Docker image to use for the jobs | `string` | n/a | yes |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | Environment variables to set for all jobs | `map(string)` | `{}` | no |
| <a name="input_job_name_prefix"></a> [job\_name\_prefix](#input\_job\_name\_prefix) | Prefix for job names (e.g., 'trackrat-ops') | `string` | n/a | yes |
| <a name="input_jobs"></a> [jobs](#input\_jobs) | Map of job configurations | <pre>map(object({<br/>    command               = list(string)              # Command to execute<br/>    args                  = optional(list(string))    # Command arguments<br/>    cpu_limit             = optional(string, "1")     # CPU limit (e.g., "1", "2", "4")<br/>    memory_limit          = optional(string, "2Gi")   # Memory limit (e.g., "512Mi", "1Gi", "2Gi")<br/>    max_retries           = optional(number, 3)       # Max retries on failure<br/>    task_timeout          = optional(string, "300s")  # Task timeout<br/>    environment_variables = optional(map(string), {}) # Job-specific env vars<br/>  }))</pre> | n/a | yes |
| <a name="input_labels"></a> [labels](#input\_labels) | Labels to apply to all jobs | `map(string)` | `{}` | no |
| <a name="input_location"></a> [location](#input\_location) | GCP region where jobs will be created | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | GCP project ID | `string` | n/a | yes |
| <a name="input_secret_environment_variables"></a> [secret\_environment\_variables](#input\_secret\_environment\_variables) | Secret environment variables from Secret Manager (format: secret\_name:version) | `map(string)` | `{}` | no |
| <a name="input_service_account_email"></a> [service\_account\_email](#input\_service\_account\_email) | Service account email for job execution | `string` | n/a | yes |
| <a name="input_vpc_connector_id"></a> [vpc\_connector\_id](#input\_vpc\_connector\_id) | VPC connector for private network access (optional) | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | Map of full job resource IDs |
| <a name="output_job_locations"></a> [job\_locations](#output\_job\_locations) | Map of job locations |
| <a name="output_job_names"></a> [job\_names](#output\_job\_names) | Map of job names created |
| <a name="output_job_uris"></a> [job\_uris](#output\_job\_uris) | Map of job URIs for Cloud Scheduler to invoke |
<!-- END_TF_DOCS -->