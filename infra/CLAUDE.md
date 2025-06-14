# TrackRat Infrastructure Guide for Claude

This file provides comprehensive guidance for Claude Code when working with the TrackRat GCP infrastructure and Terraform code.

## Infrastructure Overview

The TrackRat infrastructure is designed for a multi-environment deployment on Google Cloud Platform:

- **Development**: `trackrat-dev` project
- **Staging**: `trackrat-staging` project  
- **Production**: `trackrat-prod` project

## Directory Structure and Purpose

```
infra/
├── main.tf                           # Root module - orchestrates all infrastructure
├── variables.tf                      # Global variables for all environments
├── outputs.tf                        # Outputs from root module
├── setup-backend.sh                  # Script to initialize Terraform backends
├── environments/                     # Environment-specific configurations
│   ├── dev/                         # Development environment
│   │   ├── main.tf                  # Dev-specific configuration
│   │   ├── variables.tf             # Dev-specific variables
│   │   ├── outputs.tf               # Dev outputs
│   │   └── terraform.tfvars         # Dev variable values (created by setup script)
│   ├── staging/                     # Staging environment (similar structure)
│   └── prod/                        # Production environment (similar structure)
└── modules/                         # Reusable Terraform modules
    ├── apis/                        # GCP API enablement module
    ├── artifact-registry/           # Container registry module
    ├── secrets/                     # Secret Manager module
    └── vpc/                         # VPC and networking module
```

## Terraform Module Architecture

### Root Module (`main.tf`, `variables.tf`, `outputs.tf`)
- Orchestrates all infrastructure components
- Uses child modules for organization and reusability
- Defines global variables and outputs

### Environment Modules (`environments/*/`)
- Environment-specific configurations
- Each environment has its own Terraform state
- Uses the root module as a source
- Different CIDR ranges to prevent conflicts

### Child Modules (`modules/*/`)
- **apis**: Enables required GCP APIs
- **vpc**: Creates VPC, subnets, NAT, firewall rules
- **secrets**: Sets up Secret Manager for sensitive data
- **artifact-registry**: Creates Docker repositories with cleanup policies

## Key Infrastructure Components

### 1. VPC and Networking (`modules/vpc/`)
**Purpose**: Secure, isolated network infrastructure
**Resources**:
- Custom VPC network (no auto-subnets)
- Regional subnet with private Google access
- Cloud Router and NAT for outbound traffic
- Firewall rules for health checks and internal communication

**CIDR Planning**:
- Dev: 10.1.0.0/16 (subnet: 10.1.1.0/24)
- Staging: 10.2.0.0/16 (subnet: 10.2.1.0/24)
- Prod: 10.3.0.0/16 (subnet: 10.3.1.0/24)

### 2. Secret Manager (`modules/secrets/`)
**Purpose**: Secure storage for application secrets
**Resources**:
- Secret Manager secret with auto-replication
- Initial secret version with placeholders
- Lifecycle policy to ignore changes (updated externally)

**Expected Secrets**:
```json
{
  "database_url": "postgresql://...",
  "nj_transit_api_key": "...",
  "amtrak_api_key": "..."
}
```

### 3. Artifact Registry (`modules/artifact-registry/`)
**Purpose**: Docker image storage for Cloud Run deployments
**Resources**:
- Docker repository per environment
- Cleanup policies: keep 10 recent versions, delete after 30 days
- Vulnerability scanning enabled

### 4. APIs Module (`modules/apis/`)
**Purpose**: Enable required GCP services
**APIs Enabled**:
- Cloud Run, Cloud SQL, Secret Manager
- Cloud Storage, Cloud Build
- Monitoring, Logging, Pub/Sub
- Artifact Registry, Compute Engine
- IAM and Resource Manager

## Terraform State Management

### Backend Configuration
- **Storage**: Google Cloud Storage buckets
- **Naming**: `{project-id}-terraform-state`
- **Path**: `terraform/state/default.tfstate`
- **Locking**: Enabled via GCS
- **Versioning**: Enabled with 30-day cleanup

### State Separation
Each environment has its own:
- GCS bucket for state storage
- Terraform workspace/directory
- Variable files (`terraform.tfvars`)

## Development Workflow

### When Working with Infrastructure Code

1. **Environment Setup**:
   ```bash
   cd infra
   ./setup-backend.sh  # First time only
   cd environments/dev
   terraform init
   ```

2. **Making Changes** (ALWAYS run these in order):
   ```bash
   # 1. MANDATORY: Format and validate before any changes
   make format validate
   
   # 2. Make your changes to Terraform files
   
   # 3. MANDATORY: Run comprehensive testing
   make test
   
   # 4. Plan and review changes
   make dev-plan
   
   # 5. Apply if tests pass
   make dev-apply
   ```

3. **Module Development**:
   - Modify modules in `modules/` directory
   - Always run `make test` after changes
   - Test changes in dev environment first
   - Use `make docs` to update documentation

### MANDATORY: Claude Linting Workflow

**CRITICAL**: Claude MUST run linting and testing for ANY changes to the infra directory:

#### Before Making Changes
1. **Always start with formatting and validation**:
   ```bash
   cd infra
   make format validate
   ```

#### After Making Changes
2. **MANDATORY testing sequence**:
   ```bash
   # Run quick testing (required - always works)
   make test
   
   # Optional: Run comprehensive testing (requires additional tools)
   make test-full
   
   # Individual checks (if needed):
   make format      # Format all files
   make validate    # Validate syntax
   make quick-test  # Quick validation without external tools
   make lint        # Run TFLint (requires tflint)
   make security    # Run security scan (requires checkov)
   make docs        # Generate documentation (requires terraform-docs)
   ```

#### For Environment Changes
3. **Always test plans before applying**:
   ```bash
   make dev-plan      # For development
   make staging-plan  # For staging
   make prod-plan     # For production
   ```

### Best Practices for Claude

1. **ALWAYS TEST FIRST**: Run `make test` before suggesting ANY Terraform changes
2. **Use Quick Tests**: `make test` runs reliable validation that always works
3. **Use Modules**: Don't duplicate code; create or modify modules
4. **Environment Consistency**: Ensure changes work across all environments
5. **State Safety**: Never suggest direct state manipulation
6. **Security First**: Follow principle of least privilege for IAM
7. **Documentation**: Run `make docs` after module changes (if terraform-docs available)
8. **Full Testing**: Use `make test-full` for comprehensive checks when tools are available

### Required Tools Check

Before working with infrastructure, verify tools are available:
```bash
# Check tool availability
terraform version    # Required
tflint --version     # Recommended  
checkov --version    # Recommended
terraform-docs version  # Optional but useful
```

### Linting Integration

The infrastructure includes multiple linting layers:

#### 1. Pre-commit Hooks (`.pre-commit-config.yaml`)
- Runs automatically on `git commit`
- Formats, validates, and lints code
- Prevents bad code from being committed

#### 2. Comprehensive Linting Script (`lint-and-test.sh`)
- Runs all quality checks
- Used by `make test` command
- Can be run standalone with `./lint-and-test.sh`

#### 3. Quick Testing Script (`quick-test.sh`)
- Basic validation without external dependencies
- Reliable validation that always works
- Used by `make test` command
- Run with `./quick-test.sh`

#### 4. Legacy Testing Script (`test-terraform.sh`)
- Older testing script (may have issues)
- Use `quick-test.sh` instead

#### 5. GitHub Actions (`.github/workflows/terraform-ci.yml`)
- Runs on every PR and push
- Comprehensive testing pipeline
- Blocks merges if tests fail

### Makefile Commands Reference

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `make test` | Run quick tests | **ALWAYS** after changes |
| `make test-full` | Run comprehensive tests | When all tools available |
| `make quick-test` | Run quick validation | Alternative to `make test` |
| `make format` | Format Terraform files | Before making changes |
| `make validate` | Validate syntax | After making changes |
| `make lint` | Run TFLint | For advanced linting (requires tflint) |
| `make security` | Run security scan | Before production (requires checkov) |
| `make docs` | Generate documentation | After module changes (requires terraform-docs) |
| `make dev-plan` | Plan dev environment | Before applying |
| `make dev-apply` | Apply dev environment | After successful plan |

### Error Handling

If linting fails:

1. **Format Issues**: Run `make format` to auto-fix
2. **Validation Issues**: Check syntax errors in .tf files
3. **TFLint Issues**: Review and fix reported problems
4. **Security Issues**: Address Checkov findings (may be warnings)
5. **Documentation Issues**: Run `make docs` to regenerate

### CI/CD Integration Notes

- **GitHub Actions**: Runs comprehensive validation on PRs (no automatic deployment)
- **Pre-commit**: Runs local checks before commits
- **Manual Deployment**: All infrastructure changes deployed manually for safety
- **State Management**: Each environment managed separately with manual oversight

### Deployment Strategy

**Current Approach**: Manual deployment for safety and control
- Use `make dev-plan` and `make dev-apply` for development
- Use `make staging-plan` and `make staging-apply` for staging  
- Use `make prod-plan` and `make prod-apply` for production

**Future Consideration**: Automated deployment will be implemented separately with:
- Approval workflows
- Deployment gates
- Rollback capabilities
- Enhanced monitoring

## Common Infrastructure Operations

### Adding New GCP APIs
1. Add to `modules/apis/main.tf` in the `for_each` set
2. Apply to all environments

### Modifying Network Configuration
1. Update `modules/vpc/main.tf`
2. Consider impact on existing resources
3. Test in dev environment first

### Adding New Secrets
1. Update `modules/secrets/main.tf`
2. Secrets are managed externally via Secret Manager UI or CLI
3. Don't store actual secret values in Terraform

### Creating New Modules
1. Create directory under `modules/`
2. Include `main.tf`, `variables.tf`, `outputs.tf`
3. Add module call to root `main.tf`
4. Update root `outputs.tf` if needed

## Security Considerations

### IAM and Permissions
- Use service accounts for application access
- Follow principle of least privilege
- Workload Identity for secure GKE/Cloud Run access

### Network Security
- Private subnets with NAT for outbound access
- Firewall rules restrict traffic to necessary ports
- VPC provides network isolation

### Secret Management
- All sensitive data in Secret Manager
- Secrets not stored in Terraform state
- Access controlled via IAM

## Integration with TrackRat Application

### Expected Infrastructure Outputs
The application expects these infrastructure components:
1. **VPC Network**: For Cloud Run deployment
2. **Secret Manager**: For database and API credentials
3. **Artifact Registry**: For container image storage
4. **APIs**: All required services enabled

### Environment Variables
Cloud Run services will use:
- `GCP_PROJECT_ID`: From Terraform output
- `GCP_REGION`: From Terraform output
- `SECRET_NAME`: From Secret Manager module output
- `VPC_NETWORK`: From VPC module output

## Troubleshooting Guide

### Common Terraform Issues
1. **API Not Enabled**: Check `modules/apis/` configuration
2. **Permission Denied**: Verify IAM permissions
3. **Resource Conflicts**: Check resource naming and dependencies
4. **State Lock**: Wait for operations to complete or force unlock

### GCP-Specific Issues
1. **Quota Limits**: Check GCP quotas for the region
2. **Billing**: Ensure billing is enabled for all projects
3. **Organization Policies**: Check for restrictive org policies

### Module Development Issues
1. **Circular Dependencies**: Review module dependencies
2. **Variable Validation**: Add validation rules to variables
3. **Output Dependencies**: Ensure outputs are available when needed

## Testing Infrastructure Changes

### Local Validation
```bash
terraform fmt -recursive    # Format all files
terraform validate         # Validate syntax
terraform plan             # Review planned changes
```

### Environment Testing
1. **Dev First**: Always test in development environment
2. **Staging**: Deploy to staging for integration testing
3. **Production**: Deploy to production with approval

### Rollback Strategy
1. **Terraform State**: Previous versions stored in GCS
2. **Git History**: All changes tracked in version control
3. **Manual Intervention**: Document manual steps if needed

## Future Infrastructure Needs

### Phase 2: Database Layer
- Cloud SQL PostgreSQL instances
- Private IP connectivity
- Backup and high availability configuration

### Phase 3: Application Layer
- Cloud Run services
- Load balancing and SSL certificates
- Auto-scaling configuration

### Phase 4: Monitoring Layer
- Cloud Monitoring dashboards
- Alerting policies
- Log aggregation and analysis

### Phase 5: CI/CD Layer
- Cloud Build pipelines
- Artifact promotion between environments
- Automated testing and deployment

## Quick Reference Commands

### Terraform Commands
```bash
terraform init                    # Initialize working directory
terraform plan                    # Create execution plan
terraform apply                   # Apply changes
terraform destroy                 # Destroy infrastructure
terraform state list              # List resources in state
terraform output                  # Show output values
```

### GCP Commands
```bash
gcloud config set project PROJECT_ID        # Set active project
gcloud services list --enabled              # List enabled APIs
gcloud projects get-iam-policy PROJECT_ID   # View IAM policy
gsutil ls gs://BUCKET_NAME                  # List bucket contents
```

### Environment Setup
```bash
cd infra
./setup-backend.sh                         # Setup all environments
cd environments/dev && terraform init      # Initialize dev
cd ../staging && terraform init            # Initialize staging
cd ../prod && terraform init               # Initialize prod
```

## Contact and Support

When working on infrastructure:
1. **Terraform Issues**: Check official HashiCorp documentation
2. **GCP Issues**: Consult Google Cloud documentation
3. **Module Questions**: Reference module README files
4. **State Issues**: Use caution and create backups

Remember: Infrastructure changes affect the entire application stack. Always test thoroughly and coordinate with application development.