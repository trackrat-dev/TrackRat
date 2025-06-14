# TrackRat GitHub Workflows

This directory contains GitHub Actions workflows for continuous integration and testing.

## Workflows

### 1. Backend CI (`backend-ci.yml`)
**Triggers:** Push/PR to main/develop branches with backend changes

**Jobs:**
- **test**: Runs Python unit tests and code quality checks
- **docker-build**: Builds and validates the Docker container
- **requirements-check**: Validates requirements files

### 2. Docker Build Test (`docker-build-test.yml`)
**Triggers:** Push/PR with Docker-related changes

**Focus:** Comprehensive Docker container validation
- ✅ Multi-stage build process
- ✅ Container security (non-root user)
- ✅ Python dependencies installation
- ✅ Module imports and CLI access
- ✅ Health endpoint structure
- ✅ Image size and structure

## What Gets Tested

### Container Build Validation
- Docker image builds successfully using multi-stage Dockerfile
- All inference dependencies install correctly
- Key Python modules (FastAPI, PyTorch, SQLAlchemy) import properly
- TrackCast application modules load without errors
- CLI tool (`trackcast`) is accessible
- Health check endpoint exists in application routes

### Security Validation
- Container runs as non-root user (`trackcast`)
- Required directories exist with proper permissions
- No sensitive data in container image

### Performance Validation
- Build process uses layer caching for efficiency
- Image size is reasonable for inference-only service
- Build completes within expected timeframe

## Triggering Workflows

### Automatic Triggers
Workflows run automatically on:
- Push to `main`, `develop`, or `infra-ops-*` branches
- Pull requests targeting `main` or `develop`
- Changes to relevant files (backend code, Dockerfile, requirements)

### Manual Triggers
Both workflows support manual dispatch:
```bash
# Via GitHub UI: Actions tab → Select workflow → Run workflow

# Via GitHub CLI:
gh workflow run backend-ci.yml
gh workflow run docker-build-test.yml
```

## Understanding Results

### ✅ Success Indicators
- All jobs complete with green checkmarks
- Container builds without errors
- All validation tests pass
- Build summary shows successful completion

### ❌ Common Failure Scenarios
- **Docker build fails**: Check Dockerfile syntax or dependency issues
- **Import errors**: Missing dependencies in requirements-inference.txt
- **Security failures**: Container running as root or permission issues
- **Module errors**: TrackCast application code issues

## Caching Strategy

Both workflows use Docker layer caching to speed up builds:
- Cache key based on OS and SHA
- Significant speedup on subsequent builds
- Cache automatically managed by GitHub Actions

## CI Integration

These workflows ensure that:
1. **Container images can be built** before deployment
2. **No regressions** in containerization setup
3. **Security standards** are maintained
4. **Dependencies** remain installable

This prevents broken deployments and catches containerization issues early in the development process.