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
  description = "GCE machine type for BOTH staging and production - the two environments are kept in sync on resources, and differ only in provisioning model (staging SPOT, production on-demand; see local.use_spot_vm in main.tf). t2d-standard-1 = 1 vCPU / 4 GB on the Tau/AMD Milan family: dedicated physical cores give consistent per-core latency for the FastAPI + colocated Postgres, unlike the oversubscribed e2-custom-2-4096 that regressed API responsiveness and was reverted. RAM is ample (~1.0 GB used of 4 GB). CPU is the tight dimension: on the previous t2d-standard-2, production measured a 24h mean of 35% and a peak of 54% of 2 vCPU - that peak is ~1.07 vCPU, i.e. above a single core, so bursts (scheduler collection ticks) can saturate this size. If p99 latency or scheduler task timeouts regress, move back to t2d-standard-2; that restores 2 vCPU for both environments."
  type        = string
  default     = "t2d-standard-1"
}

variable "consolidate_api_lb" {
  description = "Production cutover switch: when true, tear down this workspace's dedicated API frontend (IP, url map, proxies, forwarding rules) because apiv2.trackrat.net is served by the consolidated webpage LB (infra_v2/terraform-webpage). Flipped to true at runbook Phase 4 (webpage LB applied, apiv2 DNS on the shared IP, old forwarding rule drained) — see infra_v2/RUNBOOK-lb-consolidation.md. Flipped via a committed default change, not -var, so push-triggered applies stay consistent. No effect on staging."
  type        = bool
  default     = true
}

variable "frontend_via_cloudflare" {
  description = "Cloudflare cutover switch: when true, tear down this workspace's dedicated API frontend (IP, url map, proxies, forwarding rules) because the API is fronted by a Cloudflare Tunnel (cloudflared container) instead of a Google load balancer. This is what removes the 'Cloud Load Balancer Forwarding Rule Minimum Global' charge. Flip to true (committed default, not -var, so push-triggered applies stay consistent) ONLY after the tunnel connector is healthy and the hostname's DNS is cut over to it — see infra_v2/RUNBOOK-cloudflare-cutover.md. Applies to whichever workspace it is set in; during the staging pilot only staging has a tunnel."
  type        = bool
  default     = false
}

variable "enable_cloudflare_tunnel" {
  description = "Master on/off switch for the Cloudflare Tunnel connector (cloudflared). When false (the committed default), the startup script NEVER creates the cloudflared container, regardless of whether the trackrat-cloudflare-tunnel-token-<env> secret exists — so a dormant/invalid token can no longer crash-loop a connector (issue #1578). Activation requires BOTH this flag true AND the secret present. This gates only whether the connector runs; frontend_via_cloudflare separately controls tearing down the Google API frontend. Flip via a committed default (not -var) so push-triggered applies stay consistent, and only after a valid token is stored — see infra_v2/RUNBOOK-cloudflare-cutover.md."
  type        = bool
  default     = true
}

variable "disabled_data_sources" {
  description = "Per-environment TRACKRAT_DISABLED_DATA_SOURCES value: data_source codes fully disabled (collection, schedule generation, GTFS refresh, service-alert polling, and API serving). Keyed by environment so staging can carry a source through a soak while production stays dark — previously this was a single hardcoded literal in compute.tf shared by both workspaces, so enabling a source for a staging soak armed the next production apply to enable it too (issue #1634). Set via committed defaults, not -var: infra_v2/cloudbuild-terraform.yaml auto-applies this root on every deploy-branch push and passes only environment/project_id, so an uncommitted -var would be silently reverted by the next push. Codes must match ALL_DATA_SOURCES in the backend; an unknown code is ignored by settings.py rather than erroring, so a typo here silently ENABLES a source. See infra_v2/RUNBOOK-data-source-flags.md."
  type        = map(list(string))
  default = {
    staging    = ["BART", "WMATA", "MBTA", "METRA", "SEPTA_RR", "SEPTA_METRO"]
    production = ["BART", "WMATA", "MBTA", "METRA", "SEPTA_RR", "SEPTA_METRO"]
  }
  validation {
    condition     = alltrue([for env in ["staging", "production"] : contains(keys(var.disabled_data_sources), env)])
    error_message = "disabled_data_sources must define both 'staging' and 'production' keys."
  }
  validation {
    condition = alltrue([
      for env, codes in var.disabled_data_sources : alltrue([
        for code in codes : can(regex("^[A-Z][A-Z0-9_]*$", code))
      ])
    ])
    error_message = "disabled_data_sources codes must be uppercase data_source identifiers (e.g. SEPTA_RR)."
  }
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
