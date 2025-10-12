"""TrackRat Infrastructure-Only Release

This release definition is used for infrastructure changes that don't
require a new backend build, such as:
- Updating Cloud Run configuration (CPU, memory, env vars)
- Modifying VPC, networking, or firewall rules
- Updating Secret Manager secrets
- Changing Cloud SQL configuration
- Infrastructure fixes and updates

Use this when you only want to apply Terraform changes without building
a new Docker image.
"""

ocuroot("0.3.0")

load("/lib/terraform.star", "setup_terraform")

def apply_infrastructure(environment):
    """Apply infrastructure changes without changing the Docker image

    This retrieves the currently deployed image and re-applies Terraform
    with any infrastructure configuration changes.

    Args:
        environment: Ocuroot environment object

    Returns:
        Dictionary of Terraform outputs
    """

    print("")
    print("=" * 60)
    print("🏗️  INFRASTRUCTURE UPDATE")
    print("=" * 60)
    print("   Environment: {}".format(environment.name))
    print("   Project: {}".format(environment.attributes["gcp_project"]))
    print("")
    print("⚠️  This will apply infrastructure changes only")
    print("   The current Docker image will be preserved")
    print("")

    # Get current image from Cloud Run
    print("🔍 Retrieving current Docker image...")
    result = host.shell("""
        gcloud run services describe {} \
            --region={} \
            --project={} \
            --format='value(spec.template.spec.containers[0].image)'
    """.format(
        environment.attributes["service_name"],
        environment.attributes["gcp_region"],
        environment.attributes["gcp_project"]
    ), capture_output=True, check=False)

    if result.returncode != 0:
        # Service might not exist yet, use latest tag
        project_id = environment.attributes["gcp_project"]
        repository = environment.attributes["artifact_registry"]
        current_image = "us-central1-docker.pkg.dev/{}/{}/trackcast-inference:latest".format(
            project_id, repository
        )
        print("⚠️  Could not get current image, using latest tag")
    else:
        current_image = result.stdout.strip()

    print("   Current image: {}".format(current_image))
    print("")

    # Setup Terraform
    print("🔧 Setting up Terraform...")
    tf = setup_terraform(environment, "infra")

    # Prepare Terraform variables
    terraform_vars = {
        "project_id": environment.attributes["gcp_project"],
        "region": environment.attributes["gcp_region"],
        "zone": environment.attributes["gcp_zone"],
        "api_image_url": current_image,
        "scheduler_image_url": current_image
    }

    print("")
    print("📋 Terraform variables:")
    for k, v in terraform_vars.items():
        print("   {}: {}".format(k, v))
    print("")

    # Plan changes
    print("📝 Planning Terraform changes...")
    tf.plan(vars=terraform_vars)

    # Apply changes
    print("")
    print("⚡ Applying Terraform changes...")
    outputs = tf.apply(vars=terraform_vars)

    print("")
    print("=" * 60)
    print("✅ INFRASTRUCTURE UPDATE COMPLETE")
    print("=" * 60)

    # Get service URL
    service_url = outputs.get("trackrat_api_service_url", "")
    if service_url:
        print("🔗 Service URL: {}".format(service_url))
    else:
        print("⚠️  Service URL not found in outputs")

    return outputs

def validate_infrastructure(environment):
    """Validate infrastructure configuration without making changes

    Useful for checking what would change before applying.

    Args:
        environment: Ocuroot environment object
    """

    print("")
    print("=" * 60)
    print("🔍 INFRASTRUCTURE VALIDATION")
    print("=" * 60)
    print("   Environment: {}".format(environment.name))
    print("")

    # Get current image
    result = host.shell("""
        gcloud run services describe {} \
            --region={} \
            --project={} \
            --format='value(spec.template.spec.containers[0].image)'
    """.format(
        environment.attributes["service_name"],
        environment.attributes["gcp_region"],
        environment.attributes["gcp_project"]
    ), capture_output=True, check=False)

    if result.returncode == 0:
        current_image = result.stdout.strip()
        print("   Current image: {}".format(current_image))
    else:
        project_id = environment.attributes["gcp_project"]
        repository = environment.attributes["artifact_registry"]
        current_image = "us-central1-docker.pkg.dev/{}/{}/trackcast-inference:latest".format(
            project_id, repository
        )
        print("   Using: {}".format(current_image))

    print("")

    # Setup Terraform and run plan only
    tf = setup_terraform(environment, "infra-validate")

    terraform_vars = {
        "project_id": environment.attributes["gcp_project"],
        "region": environment.attributes["gcp_region"],
        "zone": environment.attributes["gcp_zone"],
        "api_image_url": current_image,
        "scheduler_image_url": current_image
    }

    print("📝 Running Terraform plan (no changes will be applied)...")
    tf.plan(vars=terraform_vars)

    print("")
    print("✅ Validation complete - review plan above")
    print("   To apply changes, run: ocuroot release new infra/release.ocu.star")

# ============================================================================
# RELEASE PHASES
# ============================================================================

# Phase 1: Validate (for dry-run purposes)
phase(
    "validate",
    work=[
        task(
            validate_infrastructure,
            name="validate-infra",
            environment=e
        ) for e in environments()
    ]
)

# Phase 2: Deploy to Staging
phase(
    "staging",
    work=[
        deploy(
            up=apply_infrastructure,
            environment=e
        ) for e in environments() if e.attributes.get("type") == "staging"
    ]
)

# Phase 3: Deploy to Production
phase(
    "production",
    work=[
        deploy(
            up=apply_infrastructure,
            environment=e
        ) for e in environments() if e.attributes.get("type") == "production"
    ]
)
