output "collector_cloud_run_service_url" {
  description = "URL of the deployed Collector Cloud Run service"
  value       = google_cloud_run_v2_service.collector_service.uri
}

output "collector_cloud_run_service_name" {
  description = "Name of the deployed Collector Cloud Run service"
  value       = google_cloud_run_v2_service.collector_service.name
}

output "collector_cloud_run_service_account_email" {
  description = "Email of the service account used by the Collector Cloud Run service"
  value       = local.cloud_run_sa_email
}

output "pubsub_subscription_name" {
  description = "Name of the Pub/Sub subscription created for the collector service"
  value       = google_pubsub_subscription.default.name
}

output "pubsub_subscription_topic" {
  description = "Topic for the Pub/Sub subscription"
  value       = google_pubsub_subscription.default.topic
}

output "pubsub_push_service_account_email" {
  description = "Email of the service account used by Pub/Sub to push messages to the Cloud Run service"
  value       = local.pubsub_push_sa_email
}
