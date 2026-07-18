# TrackRat V2 Variables

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "trackrat-v2"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-east4"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-east4-a"
}

variable "environment" {
  description = "Environment name (staging or production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

variable "domain" {
  description = "Domain for the API - defaults based on environment (staging.apiv2.trackrat.net or apiv2.trackrat.net)"
  type        = string
  default     = "" # Empty means use local.domain
}

variable "machine_type" {
  description = "GCE machine type. t2d-standard-2 = 2 vCPU / 8 GB on the Tau/AMD Milan family: dedicated physical cores give consistent per-core latency for the FastAPI + colocated Postgres. Reverted from e2-custom-2-4096, whose oversubscribed, variable-platform vCPUs regressed API responsiveness. T2D is fixed-shape (no custom RAM), so RAM is 8 GB though only ~1.1 GB is used."
  type        = string
  default     = "t2d-standard-2"
}

variable "consolidate_api_lb" {
  description = "Production cutover switch: when true, tear down this workspace's dedicated API frontend (IP, url map, proxies, forwarding rules) because apiv2.trackrat.net is served by the consolidated webpage LB (infra_v2/terraform-webpage). Flipped to true at runbook Phase 4 (webpage LB applied, apiv2 DNS on the shared IP, old forwarding rule drained) — see infra_v2/RUNBOOK-lb-consolidation.md. Flipped via a committed default change, not -var, so push-triggered applies stay consistent. No effect on staging."
  type        = bool
  default     = true
}

variable "disk_size_gb" {
  description = "Persistent disk size in GB"
  type        = number
  default     = 40
}

variable "snapshot_retention_days" {
  description = "Number of days to retain disk snapshots"
  type        = number
  default     = 7
}

variable "alert_email" {
  description = "Email address for uptime monitoring alerts"
  type        = string
  default     = "trackrat@andymartin.cc"
}
