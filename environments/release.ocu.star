"""TrackRat Environment Definitions

This file defines the staging and production environments for TrackRat,
including their configuration attributes and deployment characteristics.
"""

ocuroot("0.3.0")

# Staging Environment
# Used for testing changes before production deployment
register_environment(
    environment("staging", {
        # Environment type
        "type": "staging",

        # GCP Configuration
        "gcp_project": "trackrat-staging",
        "gcp_region": "us-central1",
        "gcp_zone": "us-central1-b",

        # Terraform environment directory name
        "terraform_env": "staging",

        # Service URLs
        "api_url": "https://staging.api.trackrat.net",

        # Cloud Run Configuration
        "service_name": "trackrat-api-staging",
        "min_instances": "1",
        "max_instances": "1",
        "cpu_limit": "1",
        "memory_limit": "512Mi",
        "concurrency": "100",

        # OpenTelemetry Configuration
        "otel_sample_rate": "0.2",  # Higher sampling for staging

        # Data Collection Configuration
        "discovery_interval_minutes": "30",
        "journey_update_interval_minutes": "15",

        # Deployment Configuration
        "auto_deploy": "true",
        "approval_required": "false",

        # Docker Registry
        "artifact_registry": "trackcast-inference-staging"
    })
)

# Production Environment
# Live user-facing environment with stricter controls
register_environment(
    environment("production", {
        # Environment type
        "type": "production",

        # GCP Configuration
        "gcp_project": "trackrat-prod",
        "gcp_region": "us-central1",
        "gcp_zone": "us-central1-b",

        # Terraform environment directory name
        "terraform_env": "prod",

        # Service URLs
        "api_url": "https://prod.api.trackrat.net",

        # Cloud Run Configuration
        "service_name": "trackrat-api-prod",
        "min_instances": "1",
        "max_instances": "1",
        "cpu_limit": "1",
        "memory_limit": "1Gi",
        "concurrency": "100",

        # OpenTelemetry Configuration
        "otel_sample_rate": "0.05",  # Lower sampling for production

        # Data Collection Configuration
        "discovery_interval_minutes": "20",
        "journey_update_interval_minutes": "15",

        # Deployment Configuration
        "auto_deploy": "false",  # Production requires manual approval
        "approval_required": "true",

        # Docker Registry
        "artifact_registry": "trackcast-inference-prod"
    })
)
