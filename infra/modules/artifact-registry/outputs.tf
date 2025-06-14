output "repository_id" {
  description = "ID of the Artifact Registry repository"
  value       = google_artifact_registry_repository.docker_repo.repository_id
}

output "repository_url" {
  description = "URL of the Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${google_artifact_registry_repository.docker_repo.project}/${google_artifact_registry_repository.docker_repo.repository_id}"
}