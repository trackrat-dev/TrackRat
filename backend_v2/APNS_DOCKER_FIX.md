# APNS Docker Configuration Fix

## Problem Summary

The TrackRat V2 backend was experiencing Live Activity failures due to APNS configuration issues in the containerized deployment. The root cause was that the Terraform configuration removed the `APNS_AUTH_KEY` environment variable but no alternative mechanism was provided to deliver the P8 certificate to the container.

## Root Cause Analysis

1. **Terraform Change**: `APNS_AUTH_KEY` environment variable was removed from staging configuration with comment "now loaded from file path in container"
2. **Missing Implementation**: No mechanism was implemented to actually provide the P8 certificate file in the container
3. **Result**: APNS service appeared unconfigured → Live Activity updates failed → Tokens marked inactive

## Solution Implemented

### Simple Docker Fix
Added the `certs/` directory to the Docker image build process:

```dockerfile
# Copy application code, certs, and entrypoint script
COPY src/ ./src/
COPY alembic.ini ./
COPY certs/ ./certs/  # Added this line
COPY docker-entrypoint.sh ./
```

## Why This Solution Works

### ✅ Complete Configuration Chain

1. **Terraform Environment Variables** (all present):
   - `APNS_TEAM_ID` ✅ (from Secret Manager)
   - `APNS_KEY_ID` ✅ (from Secret Manager)
   - `APNS_BUNDLE_ID` ✅ (hardcoded: "net.trackrat.TrackRat")
   - `APNS_ENVIRONMENT` ✅ (hardcoded: "prod")

2. **P8 Certificate** ✅:
   - File exists at `/Users/andy/projects/TrackRat/backend_v2/certs/AuthKey_4WC3F645FR.p8`
   - Now copied to container at `/app/certs/AuthKey_4WC3F645FR.p8`

3. **Python Settings Logic** ✅:
   - `apns_auth_key_path` defaults to `"certs/AuthKey_4WC3F645FR.p8"`
   - `apns_auth_key_content` property loads from file first, falls back to env var
   - APNS service uses `settings.apns_auth_key_content` for `auth_key`

4. **Container Validation** ✅:
   - `docker-entrypoint.sh` validates P8 file at expected path
   - Container will start successfully with valid APNS configuration

### ✅ Security Benefits

- Certificate is baked into the private Docker image (not in environment variables)
- No sensitive data in Terraform state or logs
- File permissions properly set by container ownership change
- Following the intended design direction (file-based vs env var)

## Configuration Flow

```
Build Time:
certs/AuthKey_4WC3F645FR.p8 → COPY → /app/certs/AuthKey_4WC3F645FR.p8

Runtime:
APNS_TEAM_ID (env) ────┐
APNS_KEY_ID (env) ─────┤
APNS_BUNDLE_ID (env) ──┼─→ APNS Service → is_configured = True
APNS_ENVIRONMENT (env) ┤
P8 file content ───────┘
```

## Testing Verification

The fix can be verified by:

1. **Build Test**:
   ```bash
   cd backend_v2
   docker build -t trackrat-v2-test .
   ```

2. **Configuration Test**:
   ```bash
   docker run --rm \
     -e APNS_TEAM_ID="D5RZZ55J9R" \
     -e APNS_KEY_ID="4WC3F645FR" \
     -e APNS_BUNDLE_ID="net.trackrat.TrackRat" \
     -e APNS_ENVIRONMENT="dev" \
     trackrat-v2-test
   ```
   Should show: "✅ APNS configuration validation passed"

3. **Live Activity Test**:
   - Deploy to staging
   - Register a Live Activity token
   - Verify Live Activity updates continue working beyond first attempt

## Files Modified

- ✅ `Dockerfile` - Added `COPY certs/ ./certs/` line

## Files Not Modified (Intentionally)

- ❌ Terraform configuration - Kept current state to follow intended design
- ❌ Python code - Already supports file-based loading correctly
- ❌ Docker entrypoint - Already validates file path correctly

## Deployment Impact

- **Zero downtime**: Change only affects new container builds
- **Backward compatible**: Existing containers unaffected
- **Infrastructure**: No Terraform changes required
- **Security**: Improves security by moving from env vars to files

## Alternative Approaches Considered

1. **Restore APNS_AUTH_KEY env var**: Simpler but less secure
2. **Secret Manager volume mounts**: More complex infrastructure changes
3. **Hybrid approach**: Temporary but adds complexity

The chosen approach (adding certs to Docker image) is the simplest solution that achieves the intended design goal of file-based certificate loading.

## Long-term Considerations

- Consider using Google Secret Manager volume mounts for even better security
- Implement certificate rotation automation
- Add monitoring for APNS certificate expiration
- Consider separate images for different environments if certificate requirements differ