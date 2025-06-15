output "scheduler_cloud_run_service_url" {
  description = "URL of the deployed Scheduler Cloud Run service"
  value       = google_cloud_run_v2_service.scheduler_service.uri
}

output "scheduler_cloud_run_service_name" {
  description = "Name of the deployed Scheduler Cloud Run service"
  value       = google_cloud_run_v2_service.scheduler_service.name
}

output "scheduler_cloud_run_service_account_email" {
  description = "Email of the service account used by the Scheduler Cloud Run service"
  value       = local.cloud_run_sa_email
}

output "scheduler_job_name" {
  description = "Name of the legacy Cloud Scheduler job"
  value       = var.legacy_scheduler_enabled && var.scheduler_schedule != null ? google_cloud_scheduler_job.scheduler_job[0].name : null
}

output "operations_job_names" {
  description = "Names of the operations Cloud Scheduler jobs"
  value       = { for k, v in google_cloud_scheduler_job.operations_jobs : k => v.name }
}

output "operations_job_schedules" {
  description = "Schedules of the operations Cloud Scheduler jobs"
  value       = var.scheduler_jobs
}

output "scheduler_job_service_account_email" {
  description = "Email of the service account used by the Cloud Scheduler job"
  value       = local.scheduler_job_sa_email
}
