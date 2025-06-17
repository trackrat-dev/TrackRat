# TrackRat CI/CD

Automated workflows for TrackRat train tracking system - from testing to production deployment.

## Overview

TrackRat uses GitHub Actions for fully automated CI/CD pipeline that handles:
- **Testing**: Python backend, iOS builds, infrastructure validation
- **Building**: Docker containers, iOS archives
- **Deployment**: Google Cloud Run services via Terraform
- **Monitoring**: Health checks and rollback capabilities

## Workflows

### 1. Backend CI (`backend-ci.yml`)
**Triggers:** Push/PR to main/develop branches with backend changes

**Jobs:**
- **test**: Python unit tests, linting, type checking
- **docker-build**: Multi-stage container build validation
- **requirements-check**: Dependency compatibility checks

### 2. Full Deployment (`deploy.yml`) 
**Triggers:** Push to main branch

**Complete production pipeline:**
- ✅ Build and push Docker images to Artifact Registry
- ✅ Deploy infrastructure via Terraform
- ✅ Update Cloud Run services with zero downtime
- ✅ Run database migrations automatically
- ✅ Health check validation
- ✅ Rollback on failure

### 3. Infrastructure Testing (`infra-test.yml`)
**Triggers:** Infrastructure changes

**Validation:**
- ✅ Terraform plan/validate
- ✅ Security scanning
- ✅ Cost estimation

## Deployment Architecture

### Production Environment
- **Platform**: Google Cloud Run (fully managed, auto-scaling)
- **Database**: Cloud SQL PostgreSQL with automated backups
- **Networking**: VPC with private service connectivity
- **Monitoring**: Health checks, logging, error reporting
- **Security**: Secret Manager for credentials, IAM policies

### Automated Operations
- **Data Collection**: Cloud Scheduler triggers every 1-2 minutes
- **ML Predictions**: Real-time track prediction generation
- **Database Maintenance**: Automated migrations and cleanup
- **Scaling**: Auto-scale from 0 to configured max instances
- **Recovery**: Health checks with automatic restart on failure

## Key Features

### Zero-Downtime Deployment
- Rolling updates with traffic migration
- Health check validation before full deployment
- Automatic rollback on deployment failures
- Database migrations run safely during deployment

### Multi-Environment Support
- **Development**: Local Docker containers
- **Staging**: Cloud Run with test data
- **Production**: Full infrastructure with live data

### Security & Compliance
- Container security scanning
- Secrets managed via Secret Manager
- No credentials in code or containers
- Regular dependency updates

## Monitoring & Operations

### Health Checks
- Application startup probes
- Liveness checks every 30 seconds
- Custom health endpoints validation
- Database connectivity verification

### Logging & Debugging
- Structured JSON logging
- Error aggregation and alerting
- Performance metrics tracking
- Request tracing for debugging

## Quick Start

### Local Development
```bash
# Backend
cd backend && trackcast start-api

# iOS
cd ios && open TrackRat.xcodeproj

# Web
cd webpage && python proxy.py
```

### Production Deployment
Automatic on push to main - no manual steps required.

For detailed operational procedures, see `/OPERATORS_GUIDE.md`.