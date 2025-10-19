"""TrackRat Backend Release Definition

This release definition handles:
1. Building Docker images
2. Deploying via Terraform to Cloud Run
3. Health checks and verification
4. Rollback capabilities

Note: Uses Ocuroot for deployment orchestration
"""

ocuroot("0.3.0")

load("/lib/terraform.star", "setup_terraform")
load("/lib/secrets.star", "store_output", "get_output")

# Configure state storage (use local mode for testing, git mode for production)
# For local testing: state stored in .store/ directory
# For CI/CD: set OCUROOT_LOCAL_MODE=false to use git-based state

def is_running_in_ci():
    """Detect if we're running in a CI environment (GitHub Actions)

    Returns:
        True if running in CI, False if running locally
    """
    # Check GitHub Actions specific variable (most reliable)
    github_actions = host.shell("echo ${GITHUB_ACTIONS:-}").stdout.strip()
    if github_actions == "true":
        return True

    # Check generic CI indicator
    ci = host.shell("echo ${CI:-}").stdout.strip()
    if ci == "true":
        return True

    # Check for GitHub Actions runner name (only set in GitHub runners)
    runner_name = host.shell("echo ${RUNNER_NAME:-}").stdout.strip()
    if runner_name:
        return True

    # Default: assume local environment
    return False

def build(prev_build_number=None, year=None, month=None, day=None, sha=None, gcp_project=None, environment=None, image_tag=None):
    """Build and push Docker image to Artifact Registry (local) or use pre-built image (CI)

    When running in CI (GitHub Actions):
        - Skips Docker build
        - Uses image_tag provided via OCUROOT_INPUT_image_tag
        - Returns immediately with provided tag

    When running locally:
        - Builds Docker image
        - Pushes to Artifact Registry
        - Returns newly built image tag

    Args:
        prev_build_number: Previous build number for incrementing
        year: Year for version string (defaults to current year)
        month: Month for version string (defaults to current month)
        day: Day for version string (defaults to current day)
        sha: Git commit SHA (defaults to "unknown")
        gcp_project: GCP project ID (defaults to "trackrat-staging")
        environment: Environment name (defaults to "staging")
        image_tag: Pre-built image tag (CI only, provided via OCUROOT_INPUT_image_tag)

    Returns:
        Dictionary with build outputs (build_number, image_tag, version, timestamp)
    """

    # ============================================================================
    # CI PATH: Use pre-built image from GitHub Actions
    # ============================================================================
    if is_running_in_ci():
        print("=" * 60)
        print("🔍 DETECTED CI ENVIRONMENT")
        print("=" * 60)

        # Validate that image_tag was provided by CI
        if not image_tag:
            fail("Running in CI but no image_tag provided. Please set OCUROOT_INPUT_image_tag environment variable.")

        print("📦 Using pre-built Docker image from GitHub Actions")
        print("   Image: {}".format(image_tag))
        print("")

        # Extract version from tag for consistency
        # Tag format: .../:2025.10.19-build1-abc1234
        version = image_tag.split(":")[-1] if ":" in image_tag else "unknown"

        # Return immediately without building
        return done(
            outputs={
                "build_number": prev_build_number or 0,
                "image_tag": image_tag,
                "version": version,
                "timestamp": host.shell("date -u '+%Y-%m-%d %H:%M:%S UTC'").stdout.strip(),
                "built_in_ci": True
            }
        )

    # ============================================================================
    # LOCAL PATH: Build Docker image
    # ============================================================================
    print("=" * 60)
    print("🔍 DETECTED LOCAL ENVIRONMENT")
    print("=" * 60)
    print("📦 Will build Docker image locally")
    print("")

    # Get current date if not provided
    if not year:
        year = host.shell("date +%Y").stdout.strip()
    if not month:
        month = host.shell("date +%m").stdout.strip()
    if not day:
        day = host.shell("date +%d").stdout.strip()

    # Get git SHA if not provided
    if not sha:
        sha = host.shell("git rev-parse HEAD").stdout.strip()

    # Default values
    if not gcp_project:
        gcp_project = "trackrat-staging"
    if not environment:
        environment = "staging"

    # Increment build number
    build_number = (prev_build_number or 0) + 1

    # Generate version string
    # Format: YYYY.MM.DD-buildN-githash
    version = "{}.{}.{}-build{}-{}".format(
        year,
        month,
        day,
        build_number,
        sha[:7]
    )

    # Determine project and repository
    project_id = gcp_project
    env = environment

    # Repository name based on environment
    if "staging" in env:
        repository = "trackcast-inference-staging"
    else:
        repository = "trackcast-inference-prod"

    # Full image tag
    image_tag = "us-central1-docker.pkg.dev/{}/{}/trackcast-inference:{}".format(
        project_id, repository, version
    )

    print("=" * 60)
    print("🐳 DOCKER BUILD")
    print("=" * 60)
    print("   Version: {}".format(version))
    print("   Image: {}".format(image_tag))
    print("   Build number: {}".format(build_number))
    print("")

    # Build and push with Docker buildx
    # Note: ocuroot runs from backend_v2/ directory, but Docker needs repo root
    # Note: Cache flags removed to avoid "docker driver doesn't support cache export" error
    print("📦 Building Docker image...")
    host.shell("""
        cd ../backend_v2 && \
        docker buildx build \
            --platform linux/amd64 \
            --tag {} \
            --tag us-central1-docker.pkg.dev/{}/{}/trackcast-inference:latest \
            --tag us-central1-docker.pkg.dev/{}/{}/trackcast-inference:latest-stable \
            --push \
            .
    """.format(image_tag, project_id, repository, project_id, repository))

    print("✅ Docker image built and pushed")
    print("✅ Tagged as :latest and :latest-stable for rollback")

    # Return build outputs
    return done(
        outputs={
            "build_number": build_number,
            "image_tag": image_tag,
            "version": version,
            "timestamp": host.shell("date -u '+%Y-%m-%d %H:%M:%S UTC'").stdout.strip()
        },
    )

def deploy_infrastructure(image_tag, environment):
    """Deploy backend using Terraform

    Args:
        image_tag: Docker image tag to deploy
        environment: Ocuroot environment object

    Returns:
        Dictionary of Terraform outputs
    """

    print("")
    print("=" * 60)
    print("🚀 TERRAFORM DEPLOYMENT")
    print("=" * 60)
    print("   Environment: {}".format(environment["name"]))
    print("   Project: {}".format(environment["attributes"]["gcp_project"]))
    print("   Image: {}".format(image_tag))
    print("")

    # Setup Terraform
    print("🔧 Setting up Terraform...")
    tf = setup_terraform(environment, "backend")

    # Prepare Terraform variables
    terraform_vars = {
        "project_id": environment["attributes"]["gcp_project"],
        "region": environment["attributes"]["gcp_region"],
        "zone": environment["attributes"]["gcp_zone"],
        "api_image_url": image_tag,
        "scheduler_image_url": image_tag
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
    print("✅ TERRAFORM DEPLOYMENT COMPLETE")
    print("=" * 60)

    # Extract service URL
    service_url = outputs.get("trackrat_api_service_url", "")

    if not service_url:
        # Fallback: get URL from gcloud
        print("⚠️  Service URL not in Terraform outputs, fetching from gcloud...")
        result = host.shell("""
            gcloud run services describe {} \
                --region={} \
                --project={} \
                --format='value(status.url)' 2>/dev/null || echo ''
        """.format(
            environment["attributes"]["service_name"],
            environment["attributes"]["gcp_region"],
            environment["attributes"]["gcp_project"]
        ))

        if result.stdout.strip():
            service_url = result.stdout.strip()
            outputs["trackrat_api_service_url"] = service_url

    if service_url:
        print("🔗 Service URL: {}".format(service_url))

        # Run health checks
        print("")
        print("🏥 Running health checks...")
        verify_deployment(service_url)

        # Store outputs in Secret Manager for other services
        print("")
        print("💾 Storing deployment outputs...")
        store_output("service_url", service_url, environment)
        store_output("image_tag", image_tag, environment)
        print("✅ Outputs stored in Secret Manager")
    else:
        print("⚠️  Could not determine service URL")

    return done(
        outputs=outputs,
    )

def verify_deployment(service_url):
    """Verify deployment with health checks

    Args:
        service_url: Base URL of the deployed service
    """

    health_url = "{}/health".format(service_url)

    print("   Endpoint: {}".format(health_url))
    print("   Waiting for service to be ready...")

    # Wait for service to come up
    host.shell("sleep 30")

    # Try health checks with retries
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        print("   Attempt {}/{}...".format(attempt, max_retries))

        result = host.shell(
            "curl -f -s {} 2>/dev/null || echo ''".format(health_url)
        )

        if result.stdout.strip():
            print("✅ Health check passed!")
            print("")
            print("   Response:")
            print(result.stdout)
            return

        if attempt < max_retries:
            print("   Retrying in 30 seconds...")
            host.shell("sleep 30")

    # All retries failed
    fail("❌ Health checks failed after {} attempts".format(max_retries))

def rollback_infrastructure(image_tag, environment):
    """Rollback to the previous stable version

    Args:
        image_tag: Docker image tag (ignored, we fetch from Secret Manager)
        environment: Ocuroot environment object
    """

    print("")
    print("=" * 60)
    print("⏪ ROLLBACK")
    print("=" * 60)
    print("   Environment: {}".format(environment["name"]))
    print("")

    # Get previous image from Secret Manager
    previous_image = get_output("image_tag", environment)

    if not previous_image:
        # Fallback to latest-stable tag
        project_id = environment["attributes"]["gcp_project"]
        repository = environment["attributes"]["artifact_registry"]
        previous_image = "us-central1-docker.pkg.dev/{}/{}/trackcast-inference:latest-stable".format(
            project_id, repository
        )
        print("⚠️  No previous image in Secret Manager, using latest-stable")

    print("   Rolling back to: {}".format(previous_image))

    # Setup Terraform
    tf = setup_terraform(environment, "backend")

    # Deploy previous image
    terraform_vars = {
        "project_id": environment["attributes"]["gcp_project"],
        "region": environment["attributes"]["gcp_region"],
        "zone": environment["attributes"]["gcp_zone"],
        "api_image_url": previous_image,
        "scheduler_image_url": previous_image
    }

    tf.plan(vars=terraform_vars)
    tf.apply(vars=terraform_vars)

    print("✅ Rollback complete")

# ============================================================================
# RELEASE PHASES
# ============================================================================

# Task: Build Docker image and push to Artifact Registry
# This runs before any deployment phases
# - In CI: Uses pre-built image from GitHub Actions (via OCUROOT_INPUT_image_tag)
# - Locally: Builds Docker image and pushes to registry
task(
    name="build-backend",
    fn=build,
    inputs={
        "prev_build_number": input(
            ref="./task/build-backend#output/build_number",
            default=0
        ),
        "image_tag": input(
            name="image_tag",
            description="Pre-built Docker image tag (CI only, provided by GitHub Actions)",
            default=""  # Empty string means "not provided" - only used in CI
        )
    }
)

# Phase 1: Deploy to Staging
# Deploys to staging environment automatically
phase(
    "staging",
    work=[
        deploy(
            up=deploy_infrastructure,
            down=rollback_infrastructure,
            environment=e,
            inputs={
                "image_tag": input(ref="./task/build-backend#output/image_tag")
            }
        ) for e in environments() if e.attributes.get("type") == "staging"
    ]
)

# Phase 2: Deploy to Production
# Deploys to production environment (requires approval if configured)
#phase(
#    "production",
#    work=[
#        deploy(
#            up=deploy_infrastructure,
#            down=rollback_infrastructure,
#            environment=e,
#            inputs={
#                "image_tag": input(ref="./task/build-backend#output/image_tag")
#            }
#        ) for e in environments() if e.attributes.get("type") == "production"
#    ]
#)
