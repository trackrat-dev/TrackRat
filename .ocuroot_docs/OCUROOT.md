# Ocuroot Deployment Guide

> CI/CD orchestration for TrackRat using state-aware, dependency-driven releases

**Last Updated:** October 19, 2025
**Ocuroot Version:** v0.3.16
**Deployment Status:** Production-ready for staging; production deployment configured

---

## Table of Contents

1. [What is Ocuroot?](#what-is-ocuroot)
2. [Core Concepts](#core-concepts)
3. [TrackRat Implementation](#trackrat-implementation)
4. [CI/CD Workflow](#cicd-workflow)
5. [State Management](#state-management)
6. [Release Management](#release-management)
7. [Local Development](#local-development)
8. [Troubleshooting](#troubleshooting)
9. [Reference](#reference)

---

## What is Ocuroot?

Ocuroot is a CI/CD orchestration tool that manages complex multi-environment deployments with:

- **State-Aware Deployments**: Tracks what's deployed where and when
- **Dependency-Driven**: Automatically cascades updates through dependent services
- **GitOps Workflow**: State and intent stored in Git for team collaboration
- **Multi-Phase Releases**: Build → Staging → Production with automatic progression
- **Horizontal Scaling**: Database-coordinated scheduling with row-level locking

### Why Ocuroot for TrackRat?

- **Replaces manual Terraform workflows** with automated release pipelines
- **Tracks deployment history** across staging and production
- **Automatic health verification** after deployments
- **Rollback capability** to previous versions
- **Environment-aware configuration** via attributes

---

## Core Concepts

### State vs Intent

| Concept | Description | Managed By | Modifiable |
|---------|-------------|------------|------------|
| **State** | What actually exists (deployed releases, running services) | Ocuroot | No (read-only) |
| **Intent** | What you want to exist (environments, configurations) | You | Yes (git commits) |

**Key Principle**: Ocuroot reconciles state to match intent automatically.

### Core Entities

```
Repository (TrackRat Git repo)
    ├── Package (backend_v2/release.ocu.star)
    │   ├── Release @r1 (specific commit snapshot)
    │   │   ├── Task: build (Docker image creation)
    │   │   ├── Deploy: staging (to staging environment)
    │   │   └── Deploy: production (to prod environment)
    │   └── Release @r2 (newer commit)
    └── Package (environments/release.ocu.star)
        └── Release @r1 (environment definitions)
```

### Reference Format (URIs)

Ocuroot uses URI-style paths to reference state:

```
[repo]/-/[path]/@[release]/[subpath]#[fragment]
```

**Examples:**
```bash
# Most recent build output
./call/build#output/tag

# Specific release's service URL
backend_v2/release.ocu.star/@r1/deploy/staging#output/service_url

# Environment reference (global, not repo-scoped)
@/environment/staging

# Previous build number (self-referencing)
./call/build#output/build_number
```

**Key Patterns:**
- `./` = relative to current package
- `@` = specific release identifier (e.g., `@r1`)
- `#output/` = fragment pointing to output field
- `@/environment/` = global environment reference

---

## TrackRat Implementation

### Project Structure

```
TrackRat/
├── backend_v2/
│   └── release.ocu.star          # Main deployment pipeline
├── environments/
│   └── release.ocu.star          # Environment definitions
├── lib/
│   ├── terraform.star            # Terraform wrapper library
│   └── secrets.star              # GCP Secret Manager integration
└── .github/workflows/
    └── ci-cd.yml                 # GitHub Actions integration
```

### Release Pipeline (`backend_v2/release.ocu.star`)

**Three-Phase Deployment:**

```python
ocuroot("0.3.0")

# Phase 1: Build Docker Image
task(build, name="build", inputs={
    "prev_build_number": input(ref="./call/build#output/build_number", default=0),
    "sha": input(ref="@/custom/git_sha"),
})

# Phase 2: Deploy to Staging
phase("staging", tasks=[
    deploy(
        up=deploy_infrastructure,
        down=rollback_infrastructure,
        environment=e,
        inputs={
            "image_tag": input(ref="./call/build#output/tag"),
            "gcp_project": input(ref="@/environment/staging#attributes/gcp_project"),
        }
    ) for e in environments() if e.attributes["type"] == "staging"
])

# Phase 3: Deploy to Production (commented out - requires manual trigger)
# phase("production", tasks=[...])
```

**Key Functions:**

1. **`build()`** (lines 15-116)
   - Generates version: `YYYY.MM.DD-buildN-githash`
   - Builds Docker image with `docker buildx`
   - Pushes to GCP Artifact Registry
   - Tags: `{version}`, `latest`, `latest-stable`

2. **`deploy_infrastructure()`** (lines 118-209)
   - Sets up Terraform via `lib/terraform.star`
   - Runs `terraform plan` and `terraform apply`
   - Extracts service URL from outputs
   - Runs health checks via `verify_deployment()`
   - Stores outputs in Secret Manager

3. **`verify_deployment()`** (lines 211-254)
   - Waits 30 seconds for service startup
   - Retries health check 5 times (30s intervals)
   - Validates JSON health response
   - Fails deployment if unhealthy

4. **`rollback_infrastructure()`** (lines 256-301)
   - Retrieves previous image from Secret Manager
   - Falls back to `latest-stable` tag
   - Redeploys using Terraform

### Environment Definitions (`environments/release.ocu.star`)

**Staging Configuration:**
```python
register_environment(environment(
    name="staging",
    attributes={
        "type": "staging",
        "gcp_project": "trackrat-staging",
        "gcp_region": "us-central1",
        "gcp_zone": "us-central1-b",
        "terraform_environment": "staging",
        "cloud_run_cpu": "1",
        "cloud_run_memory": "512Mi",
        "cloud_run_min_instances": "1",
        "cloud_run_max_instances": "1",
        "otel_sample_rate": "0.2",
        "discovery_interval_minutes": "30",
        "collection_interval_minutes": "15",
        "auto_deploy": True,
        "require_approval": False,
        "artifact_registry_repo": "trackcast-inference-staging",
    }
))
```

**Production Configuration:**
```python
register_environment(environment(
    name="production",
    attributes={
        "type": "production",
        "gcp_project": "trackrat-prod",
        "cloud_run_memory": "1Gi",  # Higher than staging
        "otel_sample_rate": "0.05",  # Lower sampling
        "discovery_interval_minutes": "20",  # Faster polling
        "auto_deploy": False,  # Manual deploys only
        "require_approval": True,
    }
))
```

### Library Modules

**Terraform Wrapper (`lib/terraform.star`):**
- `setup_terraform()` - Initializes Terraform with GCS backend
- `init()` - Configures backend and downloads providers
- `plan()` - Generates execution plan
- `apply()` - Applies plan and returns outputs
- `output()` - Retrieves current Terraform outputs
- Auto-installs Terraform if missing (Homebrew on macOS, apt on Linux)

**Secrets Integration (`lib/secrets.star`):**
- `get_secret()` - Retrieves secret from GCP Secret Manager
- `set_secret()` - Creates or updates secret
- `store_output()` - Stores deployment outputs for rollback
- `get_output()` - Retrieves previous deployment outputs
- `list_secrets()` - Lists secrets with optional filtering

---

## CI/CD Workflow

### GitHub Actions Integration

**Deployment Method Selection:**
```yaml
env:
  # Default method (can override via workflow_dispatch)
  DEPLOYMENT_METHOD: ocuroot
```

**Trigger Options:**
1. **Automatic** (on push to main): Uses `DEPLOYMENT_METHOD` env var
2. **Manual** (workflow_dispatch): Choose `terraform` or `ocuroot` via dropdown

### Workflow Steps (Staging)

```yaml
# 1. Install Ocuroot
- name: Setup Ocuroot
  run: |
    set -xe
    wget -q -O ocuroot.tar.gz https://github.com/ocuroot/ocuroot/releases/download/v0.3.16/ocuroot_linux-amd64.tar.gz
    tar -xzf ocuroot.tar.gz
    chmod +x ocuroot
    sudo mv ocuroot /usr/local/bin/
    ocuroot version

# 2. Initialize State
- name: Initialize Ocuroot State
  env:
    OCUROOT_LOCAL_MODE: "false"  # Use Git-based state
    OCUROOT_ENV: staging
  run: |
    # Check if environment exists
    if ! ocuroot state get @/environment/staging; then
      # Register environments if missing
      ocuroot release new environments/release.ocu.star
    fi

# 3. Deploy via Ocuroot
- name: Deploy via Ocuroot
  env:
    OCUROOT_LOCAL_MODE: "false"
    OCUROOT_ENV: staging
    OCUROOT_INPUT_gcp_project: trackrat-staging
    OCUROOT_INPUT_environment: staging
    OCUROOT_INPUT_sha: ${{ github.sha }}
  run: |
    ocuroot release new backend_v2/release.ocu.star --cascade || {
      echo "DEPLOYMENT_FAILED=true" >> $GITHUB_ENV
      exit 1
    }

# 4. Get Service URL
- name: Get Service URL
  run: |
    SERVICE_URL=$(ocuroot state get backend_v2/release.ocu.star/@/deploy/staging#output/service_url) || \
    SERVICE_URL=$(gcloud run services describe trackcast-inference \
      --region=us-central1 --format='value(status.url)')
```

### State Storage Configuration

**Git-Based State (Production):**
```python
# In release.ocu.star files
store.set(
    store.git("https://github.com/yourorg/trackrat.git", branch="ocuroot-state"),
    intent=store.git("https://github.com/yourorg/trackrat.git", branch="ocuroot-intent"),
)
```

**Environment Variable Control:**
```bash
OCUROOT_LOCAL_MODE="false"  # Git-based (team collaboration)
OCUROOT_LOCAL_MODE="true"   # Filesystem (local testing)
```

**Best Practices:**
- **State branch**: Managed only by Ocuroot (read-only for humans)
- **Intent branch**: Modified by humans (environments, config)
- **Separate branches**: Prevents conflicts and tracks changes clearly

---

## State Management

### Querying State

```bash
# Get environment configuration
ocuroot state get @/environment/staging

# Get most recent build output
ocuroot state get backend_v2/release.ocu.star/@/call/build#output/tag

# Get specific release's service URL
ocuroot state get backend_v2/release.ocu.star/@r5/deploy/staging#output/service_url

# Find all deployments to production
ocuroot state match "**/deploy/production"

# Find all releases at specific commit
ocuroot state match "backend_v2/release.ocu.star/@*/commit/abc123..."
```

### Modifying Intent

```bash
# Update environment attributes
ocuroot state set -f=json "@/environment/staging" \
  '{"attributes": {"cloud_run_memory": "1Gi"}, "name": "staging"}'

# Delete environment (triggers cleanup)
ocuroot state delete @/environment/old-staging

# Apply intent changes to state
ocuroot work cascade
```

### Web UI

```bash
# Launch web interface at http://localhost:3000
ocuroot state view
```

**Features:**
- Browse releases, deployments, environments
- View task outputs and logs
- Inspect dependency graph
- Search state with glob patterns

---

## Release Management

### Creating Releases

**Automatic (on commit):**
```bash
# CI automatically runs on push to main
git push origin main
# → Triggers: ocuroot release new backend_v2/release.ocu.star --cascade
```

**Manual (local):**
```bash
# Create new release at current commit
ocuroot release new backend_v2/release.ocu.star

# With cascade (execute dependent work)
ocuroot release new backend_v2/release.ocu.star --cascade

# Force new release at same commit (for testing)
ocuroot release new backend_v2/release.ocu.star --force
```

### Retrying Failed Releases

```bash
# Retry most recent release
ocuroot release retry backend_v2/release.ocu.star

# Retry specific release
ocuroot release retry backend_v2/release.ocu.star/@r3
```

### Rollback

**Automatic (via down function):**
```bash
# Triggers rollback_infrastructure() function
ocuroot release rollback backend_v2/release.ocu.star staging
```

**Manual (redeploy previous version):**
```bash
# Get previous version
PREV_TAG=$(ocuroot state get backend_v2/release.ocu.star/@r4/call/build#output/tag)

# Redeploy via Terraform directly
cd infra/environments/staging
terraform apply -var="api_image_url=.../$PREV_TAG"
```

### Cascading Updates

When you use `--cascade`:
1. Release executes all phases sequentially
2. After each task completes, Ocuroot checks for dependent tasks
3. If output value differs from previous, dependent tasks re-execute
4. Updates propagate through entire dependency graph

**Example Dependency Chain:**
```
build → staging → production
      ↓
   frontend → cdn
```

When `build` outputs new image tag, `staging`, `production`, and `frontend` automatically redeploy.

---

## Local Development

### Installation

**macOS:**
```bash
brew install ocuroot/tap/ocuroot
```

**Linux:**
```bash
wget https://github.com/ocuroot/ocuroot/releases/download/v0.3.16/ocuroot_linux-amd64.tar.gz
tar -xzf ocuroot_linux-amd64.tar.gz
chmod +x ocuroot
sudo mv ocuroot /usr/local/bin/
ocuroot version  # Verify installation
```

### Local Testing Workflow

**1. Use Local State (Safe Testing):**
```bash
export OCUROOT_LOCAL_MODE=true
export OCUROOT_ENV=staging

# Register environments
ocuroot release new environments/release.ocu.star

# Verify registration
ocuroot state get @/environment/staging
```

**2. Test Build Phase Only:**
```bash
# Authenticate to GCP
gcloud auth application-default login
gcloud auth configure-docker us-central1-docker.pkg.dev

# Set inputs
export OCUROOT_INPUT_gcp_project=trackrat-staging
export OCUROOT_INPUT_environment=staging
export OCUROOT_INPUT_sha=$(git rev-parse HEAD)

# Run build only (no deployment)
ocuroot release new backend_v2/release.ocu.star --phase build
```

**3. Dry-Run Deployment:**
```bash
# Preview work without executing
ocuroot work cascade --dryrun
```

**4. Test Terraform Plan:**
```bash
cd infra/environments/staging
terraform init
terraform plan \
  -var="project_id=trackrat-staging" \
  -var="api_image_url=us-central1-docker.pkg.dev/trackrat-staging/trackcast-inference-staging/trackcast-inference:test"
```

### Authentication

**GitHub PAT (Personal Access Token):**
```bash
# Required permissions: repo (full control)
export GH_TOKEN=ghp_your_token_here

# Test access
ocuroot release new backend_v2/release.ocu.star --dryrun
```

**GCP Service Account:**
```bash
# For Terraform operations
gcloud auth application-default login

# For Docker operations
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Troubleshooting

### Common Issues

**1. "Package not found" error:**
```bash
# Ensure you're in the repo root
cd /Users/andy/projects/TrackRat

# Verify file exists
ls backend_v2/release.ocu.star

# Check ocuroot version declaration
grep 'ocuroot(' backend_v2/release.ocu.star
```

**2. State initialization fails:**
```bash
# Check OCUROOT_LOCAL_MODE is set
echo $OCUROOT_LOCAL_MODE

# For Git mode, verify branch exists
git branch -r | grep ocuroot-state

# Create branches if missing
git checkout -b ocuroot-state
git push -u origin ocuroot-state
git checkout -b ocuroot-intent
git push -u origin ocuroot-intent
git checkout main
```

**3. Missing dependency values:**
```bash
# Check if dependency exists in state
ocuroot state get ./call/build#output/tag

# If missing, ensure default is set in inputs:
# inputs={"tag": input(ref="./call/build#output/tag", default="latest")}
```

**4. Deployment fails health checks:**
```bash
# Check service URL
gcloud run services describe trackcast-inference \
  --region=us-central1 --format='value(status.url)'

# Test health endpoint manually
curl -v https://your-service-url/health

# Check Cloud Run logs
gcloud run services logs read trackcast-inference --region=us-central1 --limit=50
```

**5. Terraform state lock errors:**
```bash
# Check GCS bucket for lock
gsutil ls gs://trackrat-terraform-state/staging/

# Force unlock (use with caution!)
cd infra/environments/staging
terraform force-unlock LOCK_ID
```

### Debug Commands

```bash
# View detailed release status
ocuroot release show backend_v2/release.ocu.star

# View task logs
ocuroot state get backend_v2/release.ocu.star/@r1/call/build/1/logs

# List all releases
ocuroot state match "backend_v2/release.ocu.star/@*"

# Check environment registration
ocuroot state match "@/environment/*"

# View dependency graph
ocuroot state view  # Web UI with graph visualization
```

### CI/CD Debugging

**Check workflow logs:**
```bash
# Via GitHub CLI
gh run list --workflow=ci-cd.yml --limit=5
gh run view <run-id> --log

# Check specific job
gh run view <run-id> --job=deploy-staging --log
```

**Verify environment variables:**
```yaml
# Add debug step to workflow
- name: Debug Environment
  run: |
    echo "DEPLOYMENT_METHOD=$DEPLOYMENT_METHOD"
    echo "OCUROOT_ENV=$OCUROOT_ENV"
    echo "OCUROOT_LOCAL_MODE=$OCUROOT_LOCAL_MODE"
    ocuroot version
```

---

## Reference

### Key Commands

| Command | Description |
|---------|-------------|
| `ocuroot release new <path>` | Create new release at current commit |
| `ocuroot release new <path> --cascade` | Create release and execute dependent work |
| `ocuroot release retry <path>` | Retry failed release |
| `ocuroot release rollback <path> <env>` | Rollback deployment to previous version |
| `ocuroot work cascade` | Execute all outstanding work (intent changes) |
| `ocuroot state get <ref>` | Get document at reference |
| `ocuroot state set <ref> <json>` | Set intent document |
| `ocuroot state match <pattern>` | Search state with glob pattern |
| `ocuroot state view` | Launch web UI |
| `ocuroot state apply` | Apply intent changes to state |

### Input Configuration Patterns

**Self-Referencing (Build Numbers):**
```python
inputs={
    "prev_build_number": input(
        ref="./call/build#output/build_number",
        default=0  # Required for first run
    ),
}
```

**Cross-Package Dependencies:**
```python
inputs={
    "backend_url": input(
        ref="backend/release.ocu.star/@/deploy/staging#output/service_url"
    ),
}
```

**Environment Attributes:**
```python
inputs={
    "gcp_project": input(
        ref="@/environment/staging#attributes/gcp_project"
    ),
}
```

**Custom State:**
```python
inputs={
    "git_sha": input(ref="@/custom/git_sha"),
}
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OCUROOT_LOCAL_MODE` | State storage mode | `false` (Git), `true` (filesystem) |
| `OCUROOT_ENV` | Target environment | `staging`, `production` |
| `OCUROOT_INPUT_*` | Task input values | `OCUROOT_INPUT_gcp_project=trackrat-staging` |
| `GH_TOKEN` | GitHub PAT for Git operations | `ghp_...` |

### File Structure Reference

```
release.ocu.star
├── ocuroot("0.3.0")              # Version declaration (required)
├── store.set(...)                # State storage configuration
├── remotes([...])                # Git remote configuration
├── def task_function(...):       # Task implementation
│   └── return done(output={...}) # Task output
├── task(fn, name, inputs)        # Task registration
├── deploy(up, down, env, inputs) # Deployment registration
└── phase(name, tasks=[...])      # Phase grouping
```

### Best Practices

1. **Always use `--cascade`** for production deployments to ensure dependent work executes
2. **Separate state and intent branches** to prevent conflicts
3. **Use environment attributes** for filtering rather than hardcoded names
4. **Include health checks** in deployment functions
5. **Store rollback data** in Secret Manager or state outputs
6. **Test locally with `OCUROOT_LOCAL_MODE=true`** before pushing
7. **Use `--dryrun`** before destructive operations
8. **Version your release files** with `ocuroot("X.Y.Z")` declaration
9. **Provide defaults** for self-referencing inputs
10. **Document custom attributes** in environment definitions

### Common Patterns

**Multi-Environment Deployment:**
```python
for e in environments():
    if e.attributes["type"] in ["staging", "production"]:
        deploy(up=deploy_fn, down=rollback_fn, environment=e, ...)
```

**Conditional Deployments:**
```python
if environment.attributes["auto_deploy"]:
    # Auto-deploy to staging
else:
    # Require manual approval for production
    pass
```

**Version Tagging:**
```python
def build():
    version = "{}.{}.{}-build{}-{}".format(
        year, month, day, build_number, sha[:7]
    )
    # Tag image with version, latest, latest-stable
```

---

## Additional Resources

- **Ocuroot Documentation**: `/Users/andy/projects/TrackRat/_ocuroot_docs/`
- **Release Pipeline**: `/Users/andy/projects/TrackRat/backend_v2/release.ocu.star`
- **Environment Definitions**: `/Users/andy/projects/TrackRat/environments/release.ocu.star`
- **CI/CD Workflow**: `/Users/andy/projects/TrackRat/.github/workflows/ci-cd.yml`
- **Terraform Library**: `/Users/andy/projects/TrackRat/lib/terraform.star`
- **Secrets Library**: `/Users/andy/projects/TrackRat/lib/secrets.star`

---

**Last Reviewed:** October 19, 2025
**Maintainer:** Andy (TrackRat Project)
