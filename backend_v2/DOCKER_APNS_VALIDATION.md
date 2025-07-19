# Docker APNS Validation Implementation

## Summary

Updated the TrackRat V2 backend container to validate APNS configuration at startup and exit immediately if not properly configured. This ensures that Live Activities will work correctly in production environments.

## Changes Made

### 1. Docker Entrypoint Script (`docker-entrypoint.sh`)
- **Comprehensive APNS validation** similar to `run_backend.sh`
- **Validates P8 certificate file** existence, format, and loadability
- **Validates environment variables** (TEAM_ID, KEY_ID, BUNDLE_ID, ENVIRONMENT)
- **Exits with clear error messages** if validation fails
- **Provides detailed guidance** on required configuration

### 2. Updated Dockerfile
- **Added entrypoint script** to container
- **Made script executable** during build
- **Replaced simple CMD** with validation-enabled ENTRYPOINT

### 3. Docker Compose Example (`docker-compose.example.yml`)
- **Complete production-ready example** with all required environment variables
- **Volume mounts** for APNS certificate and database persistence
- **Health checks** and restart policies
- **Clear documentation** in comments

### 4. Test Script (`test-docker-apns.sh`)
- **Automated testing** of APNS validation logic
- **Verifies container exits** when APNS is misconfigured
- **Tests multiple failure scenarios** (missing vars, invalid lengths, missing cert)

### 5. Updated Documentation (`README.md`)
- **Added APNS as required prerequisite**
- **Comprehensive APNS configuration section**
- **Docker deployment examples** with proper APNS setup
- **Container validation explanation**

## Validation Behavior

### ✅ What Gets Validated
- APNS P8 certificate file exists and is readable
- P8 file has valid PEM format (BEGIN/END PRIVATE KEY)
- P8 file size is reasonable (200-400 bytes)
- P8 certificate loads successfully with cryptography library
- APNS_TEAM_ID is exactly 10 characters
- APNS_KEY_ID is exactly 10 characters  
- APNS_BUNDLE_ID contains only valid characters
- APNS_ENVIRONMENT is either "dev" or "prod"

### ❌ Container Exit Conditions
- Any required APNS environment variable is missing
- Environment variables have invalid format/length
- P8 certificate file is missing or unreadable
- P8 certificate has invalid format
- P8 certificate fails to load with cryptography

### 💡 Error Messages
- Clear, actionable error messages explaining what's wrong
- Detailed guidance on required environment variables
- Instructions for certificate placement
- Helpful formatting with emojis for better visibility

## Usage Examples

### Development with APNS
```bash
# Set required environment variables
export APNS_TEAM_ID="D5RZZ55J9R"
export APNS_KEY_ID="4WC3F645FR"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"
export APNS_ENVIRONMENT="dev"

# Place certificate
mkdir -p certs
cp AuthKey_4WC3F645FR.p8 certs/

# Run container
docker run -p 8000:8000 \
  -e APNS_TEAM_ID -e APNS_KEY_ID -e APNS_BUNDLE_ID -e APNS_ENVIRONMENT \
  -v $(pwd)/certs:/app/certs:ro \
  trackrat-v2
```

### Testing Validation
```bash
# Run test suite to verify validation works
./test-docker-apns.sh

# Test specific failure case
docker run --rm \
  -e APNS_TEAM_ID="INVALID" \
  trackrat-v2
# Should exit with clear error about TEAM_ID length
```

## Benefits

1. **Production Safety**: Ensures Live Activities work in production
2. **Clear Error Messages**: Developers know exactly what's wrong
3. **Fast Failure**: Container exits immediately rather than running broken
4. **Comprehensive Validation**: Catches common configuration mistakes
5. **Documentation**: Clear examples and guidance for proper setup

## Files Modified/Created

- ✅ `docker-entrypoint.sh` - New validation script
- ✅ `Dockerfile` - Updated to use entrypoint
- ✅ `docker-compose.example.yml` - Production example
- ✅ `test-docker-apns.sh` - Validation testing
- ✅ `README.md` - Updated documentation
- ✅ `DOCKER_APNS_VALIDATION.md` - This summary

The container now provides the same level of APNS validation as the local `run_backend.sh` script, ensuring consistency between development and production environments.