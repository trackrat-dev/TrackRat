# TrackRat Infrastructure

This directory contains the Terraform infrastructure code for deploying TrackRat to Google Cloud Platform (GCP). The infrastructure is organized into reusable modules and environment-specific configurations.

## Directory Structure

```
infra/
├── main.tf                    # Main Terraform configuration
├── variables.tf               # Global variables
├── outputs.tf                 # Global outputs
├── setup-backend.sh           # Script to setup Terraform backends
├── environments/              # Environment-specific configurations
│   ├── dev/                   # Development environment
│   ├── staging/               # Staging environment
│   └── prod/                  # Production environment
└── modules/                   # Reusable Terraform modules
    ├── apis/                  # GCP API enablement
    ├── artifact-registry/     # Docker image registry
    ├── secrets/               # Secret Manager configuration
    └── vpc/                   # VPC and networking
```

## Prerequisites

1. **Google Cloud SDK**: Install and authenticate with `gcloud`
2. **Terraform**: Install Terraform >= 1.0
3. **GCP Projects**: Create the following projects:
   - `trackrat-dev` (Development)
   - `trackrat-staging` (Staging)
   - `trackrat-prod` (Production)
4. **Permissions**: Ensure you have appropriate IAM permissions in each project

## Quick Start

### 1. Install Required Tools

Install the necessary tools for infrastructure management:

```bash
# Install Terraform
# See: https://www.terraform.io/downloads.html

# Install additional tools (optional but recommended)
pip install checkov pre-commit
go install github.com/terraform-docs/terraform-docs@latest

# Install pre-commit hooks
cd infra
make pre-commit-install
```

### 2. Setup Terraform Backend

Run the setup script to create Cloud Storage buckets for Terraform state:

```bash
cd infra
./setup-backend.sh
```

This script will:
- Create Cloud Storage buckets for Terraform state
- Enable required APIs
- Generate `terraform.tfvars` files for each environment

### 3. Lint and Test Infrastructure

Before deploying, always run linting and testing:

```bash
# Run comprehensive linting and testing
make test

# Or run individual checks
make format      # Format Terraform files
make validate    # Validate syntax
make lint        # Run full linting suite
make security    # Run security scan
make docs        # Generate documentation
```

### 4. Deploy Infrastructure

Deploy to the development environment:

```bash
# Using Make (recommended)
make dev-plan    # Plan dev environment
make dev-apply   # Apply dev environment

# Or using Terraform directly
cd environments/dev
terraform init
terraform plan
terraform apply
```

Repeat for staging and production environments as needed.

## Architecture Overview

The infrastructure creates the following resources for each environment:

### Networking
- **VPC Network**: Custom VPC with regional subnets
- **Cloud NAT**: Outbound internet access for private resources
- **Firewall Rules**: Security rules for health checks and internal communication

### Security
- **Secret Manager**: Secure storage for application secrets and API keys
- **IAM**: Service accounts and permissions following least privilege principle

### Container Registry
- **Artifact Registry**: Docker image storage with automatic cleanup policies
- **Vulnerability Scanning**: Enabled for all pushed images

### APIs
- Cloud Run API
- Cloud SQL Admin API
- Secret Manager API
- Cloud Storage API
- Cloud Build API
- Monitoring and Logging APIs
- Pub/Sub API
- Artifact Registry API

## Environment Configuration

Each environment uses different network CIDR ranges to avoid conflicts:

| Environment | VPC CIDR     | Subnet CIDR  | Project ID       |
|-------------|--------------|--------------|------------------|
| Development | 10.1.0.0/16  | 10.1.1.0/24  | trackrat-dev     |
| Staging     | 10.2.0.0/16  | 10.2.1.0/24  | trackrat-staging |
| Production  | 10.3.0.0/16  | 10.3.1.0/24  | trackrat-prod    |

## Linting and Testing

### Automated Quality Checks

The infrastructure includes comprehensive linting and testing tools:

#### Available Tools

1. **Terraform Format**: Ensures consistent code formatting
2. **Terraform Validate**: Validates syntax and configuration
3. **TFLint**: Advanced linting with Google Cloud rules
4. **Checkov**: Security scanning for misconfigurations
5. **terraform-docs**: Automatic documentation generation
6. **Pre-commit hooks**: Runs checks before commits

#### Quick Commands

```bash
# Run all checks
make test

# Individual checks
make format        # Format all .tf files
make validate      # Validate syntax
make lint          # Run TFLint
make security      # Run Checkov security scan
make docs          # Generate documentation

# Environment-specific operations
make dev-plan      # Plan dev environment
make staging-plan  # Plan staging environment
make prod-plan     # Plan production environment
```

#### CI/CD Integration

- **GitHub Actions**: Automatic validation on PRs and merges (linting, testing, validation)
- **Pre-commit**: Local checks before commits
- **Manual Deployment**: Infrastructure changes deployed manually for safety

#### Testing Scripts

- `./lint-and-test.sh`: Comprehensive testing script
- `./test-terraform.sh`: Quick validation without GCP auth
- `Makefile`: Convenient command shortcuts

### Code Quality Standards

All Terraform code must:
- Pass `terraform fmt -check`
- Pass `terraform validate` 
- Pass TFLint rules
- Have no high-severity security issues
- Include proper documentation

## Terraform State Management

- **Backend**: Google Cloud Storage
- **State Locking**: Enabled via Cloud Storage
- **Versioning**: Enabled with automatic cleanup after 30 days
- **Separation**: Each environment has its own state file

## Security Best Practices

1. **Least Privilege**: IAM permissions are minimally scoped
2. **Network Security**: VPC provides network isolation
3. **Secret Management**: All sensitive data stored in Secret Manager
4. **State Security**: Terraform state is stored securely in GCS

## Customization

### Variables

Key variables can be customized in each environment's `terraform.tfvars`:

```hcl
project_id = "your-project-id"
region     = "us-east1"
zone       = "us-east1-b"
```

### Modules

The infrastructure is built using modular components. You can modify individual modules without affecting others:

- `modules/vpc/`: Modify networking configuration
- `modules/secrets/`: Add or modify secrets
- `modules/artifact-registry/`: Adjust container registry settings
- `modules/apis/`: Add or remove required APIs

## Common Operations

### View Resources

```bash
terraform state list
terraform show
```

### Update Infrastructure

```bash
terraform plan
terraform apply
```

### Destroy Environment

```bash
terraform destroy
```

### Import Existing Resources

If you have existing GCP resources, you can import them:

```bash
terraform import google_compute_network.vpc projects/PROJECT_ID/global/networks/NETWORK_NAME
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure your user/service account has the required IAM permissions
2. **API Not Enabled**: Run `gcloud services enable API_NAME` for missing APIs
3. **Resource Already Exists**: Use `terraform import` to bring existing resources under management
4. **State Lock**: If state is locked, check for running operations or force unlock if necessary

### Useful Commands

```bash
# Check current project
gcloud config get-value project

# List enabled APIs
gcloud services list --enabled

# Check IAM permissions
gcloud projects get-iam-policy PROJECT_ID

# Force unlock state (use with caution)
terraform force-unlock LOCK_ID
```

## Next Steps

After deploying the base infrastructure:

1. **Phase 2**: Deploy Cloud SQL for PostgreSQL
2. **Phase 3**: Configure Cloud Run services
3. **Phase 4**: Set up monitoring and alerting
4. **Phase 5**: Configure CI/CD pipelines

## Support

For infrastructure-related questions or issues:
1. Check the troubleshooting section above
2. Review Terraform logs for detailed error messages
3. Consult the CLAUDE.md file for AI assistance guidelines