output "job_names" {
  description = "Map of job names created"
  value = {
    for job_key, job in google_cloud_run_v2_job.operation_jobs :
    job_key => job.name
  }
}

output "job_ids" {
  description = "Map of full job resource IDs"
  value = {
    for job_key, job in google_cloud_run_v2_job.operation_jobs :
    job_key => job.id
  }
}

output "job_locations" {
  description = "Map of job locations"
  value = {
    for job_key, job in google_cloud_run_v2_job.operation_jobs :
    job_key => job.location
  }
}

output "job_uris" {
  description = "Map of job URIs for Cloud Scheduler to invoke"
  value = {
    for job_key, job in google_cloud_run_v2_job.operation_jobs :
    job_key => "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${job.location}/jobs/${job.name}:run"
  }
}