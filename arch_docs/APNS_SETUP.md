# APNS Setup Guide

This guide covers setting up Apple Push Notification Service (APNS) for TrackRat's Live Activities and push notifications.

## Overview

TrackRat supports two APNS authentication methods:
1. **Auth Key (Recommended)**: Uses a `.p8` file with JWT authentication
2. **Certificate**: Uses `.pem` certificate and private key files

## Method 1: Auth Key Setup (Recommended)

### 1. Generate APNS Auth Key in Apple Developer Portal

1. Log in to [Apple Developer Portal](https://developer.apple.com)
2. Go to **Certificates, Identifiers & Profiles** > **Keys**
3. Click the **+** button to create a new key
4. Enter a key name (e.g., "TrackRat APNS Key")
5. Check **Apple Push Notifications service (APNs)**
6. Click **Continue** and **Register**
7. Download the `.p8` file (e.g., `AuthKey_ABC123DEF4.p8`)
8. Note the **Key ID** (e.g., `ABC123DEF4`)
9. Note your **Team ID** (found in membership details)

### 2. Configure Environment Variables

```bash
# Required for Auth Key authentication
export APNS_TEAM_ID="YOUR_TEAM_ID"           # 10-character Team ID
export APNS_KEY_ID="ABC123DEF4"              # 10-character Key ID  
export APNS_AUTH_KEY_PATH="/path/to/AuthKey_ABC123DEF4.p8"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"

# Environment selection
export TRACKCAST_ENV="prod"  # Use "dev" for sandbox, "prod" for production
```

### 3. File Placement

Place the `.p8` file in a secure location accessible to your application:

```bash
# Example directory structure
/app/
├── certs/
│   └── AuthKey_ABC123DEF4.p8
└── ...

# Set the path accordingly
export APNS_AUTH_KEY_PATH="/app/certs/AuthKey_ABC123DEF4.p8"
```

## Method 2: Certificate Setup (Alternative)

### 1. Generate Certificate in Apple Developer Portal

1. Go to **Certificates, Identifiers & Profiles** > **Certificates**
2. Click **+** to create a new certificate
3. Select **Apple Push Notification service SSL (Sandbox & Production)**
4. Choose your App ID (com.andymartin.TrackRat)
5. Upload a Certificate Signing Request (CSR)
6. Download the certificate (e.g., `aps.cer`)

### 2. Convert to PEM Format

```bash
# Convert certificate to PEM
openssl x509 -inform DER -outform PEM -in aps.cer -out aps_cert.pem

# Convert private key to PEM (if needed)
openssl rsa -in private_key.p12 -out aps_key.pem
```

### 3. Configure Environment Variables

```bash
# Required for certificate authentication
export APNS_CERT_PATH="/path/to/aps_cert.pem"
export APNS_KEY_PATH="/path/to/aps_key.pem"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"

# Environment selection
export TRACKCAST_ENV="prod"  # Use "dev" for sandbox, "prod" for production
```

## Docker Configuration

### Dockerfile Example

```dockerfile
# Copy certificates into container
COPY certs/ /app/certs/

# Set environment variables
ENV APNS_TEAM_ID="YOUR_TEAM_ID"
ENV APNS_KEY_ID="ABC123DEF4"
ENV APNS_AUTH_KEY_PATH="/app/certs/AuthKey_ABC123DEF4.p8"
ENV APNS_BUNDLE_ID="com.andymartin.TrackRat"
ENV TRACKCAST_ENV="prod"
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  trackcast:
    image: trackcast:latest
    environment:
      - APNS_TEAM_ID=${APNS_TEAM_ID}
      - APNS_KEY_ID=${APNS_KEY_ID}
      - APNS_AUTH_KEY_PATH=/app/certs/AuthKey_ABC123DEF4.p8
      - APNS_BUNDLE_ID=net.trackrat.TrackRat
      - TRACKCAST_ENV=prod
    volumes:
      - ./certs:/app/certs:ro
```

## Cloud Run Deployment

### Using Google Secret Manager

1. Store the Auth Key in Secret Manager:

```bash
# Create secret
gcloud secrets create apns-auth-key --data-file=AuthKey_ABC123DEF4.p8

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding apns-auth-key \
    --member="serviceAccount:YOUR-PROJECT@appspot.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

2. Mount as volume in Cloud Run:

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/secrets: |
          /app/certs/apns-key.p8:apns-auth-key:latest
    spec:
      containers:
      - image: gcr.io/YOUR-PROJECT/trackcast:latest
        env:
        - name: APNS_TEAM_ID
          value: "YOUR_TEAM_ID"
        - name: APNS_KEY_ID
          value: "ABC123DEF4"
        - name: APNS_AUTH_KEY_PATH
          value: "/app/certs/apns-key.p8"
        - name: APNS_BUNDLE_ID
          value: "com.andymartin.TrackRat"
        - name: TRACKCAST_ENV
          value: "prod"
```

## Environment Configuration Summary

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `APNS_TEAM_ID` | Yes (Auth Key) | Apple Developer Team ID | `ABCD123456` |
| `APNS_KEY_ID` | Yes (Auth Key) | APNS Auth Key ID | `ABC123DEF4` |
| `APNS_AUTH_KEY_PATH` | Yes (Auth Key) | Path to .p8 file | `/app/certs/AuthKey_ABC123DEF4.p8` |
| `APNS_CERT_PATH` | Yes (Cert) | Path to certificate PEM | `/app/certs/aps_cert.pem` |
| `APNS_KEY_PATH` | Yes (Cert) | Path to private key PEM | `/app/certs/aps_key.pem` |
| `APNS_BUNDLE_ID` | Yes | iOS app bundle identifier | `net.trackrat.TrackRat` |
| `TRACKCAST_ENV` | Yes | Environment (dev/prod) | `prod` |

## Testing Configuration

### 1. Check Configuration Status

The APNS service will log its configuration status on startup:

```
INFO - APNS service initialized for production environment
```

Or if misconfigured:

```
WARNING - APNS configuration incomplete - notifications will use mock mode
```

### 2. Test with Mock Mode

If configuration is incomplete, the service automatically falls back to mock mode:

```
INFO - [MOCK] APNS Request (Live Activity: True):
INFO - [MOCK] Token: 12345678...
INFO - [MOCK] Payload: {...}
```

### 3. Verify Real APNS Requests

With proper configuration, you'll see:

```
INFO - APNS notification sent successfully (Live Activity: True) to 12345678...
```

## Troubleshooting

### Common Issues

1. **"APNS configuration incomplete"**
   - Check that all required environment variables are set
   - Verify file paths are correct and files exist
   - Ensure proper file permissions

2. **"Failed to generate JWT token"**
   - Verify the .p8 file format is correct
   - Check file permissions (readable by application)
   - Confirm TEAM_ID and KEY_ID are correct

3. **"APNS request forbidden (403)"**
   - Check bundle ID matches your app
   - Verify Auth Key has APNS permissions
   - Confirm Team ID is correct

4. **"APNS token is no longer valid (410)"**
   - Device token has been invalidated
   - App was uninstalled or data was cleared
   - Token should be removed from database

### Debug Mode

Enable debug logging to see detailed APNS request information:

```bash
export LOG_LEVEL=DEBUG
```

## Security Best Practices

1. **File Permissions**: Restrict access to certificate files
   ```bash
   chmod 600 /app/certs/AuthKey_ABC123DEF4.p8
   ```

2. **Environment Variables**: Use secure secret management systems
   - Google Secret Manager for Cloud Run
   - Kubernetes Secrets for K8s
   - AWS Parameter Store for EC2

3. **Certificate Rotation**: 
   - Auth Keys don't expire but can be revoked
   - Certificates expire and need renewal
   - Monitor expiration dates

4. **Access Control**: 
   - Limit who can access certificates
   - Use service accounts with minimal permissions
   - Audit certificate access

## Migration from Mock to Production

1. **Deploy with Mock Mode**: First deploy with incomplete configuration to verify everything else works
2. **Add Configuration**: Add APNS configuration incrementally
3. **Test in Sandbox**: Use `TRACKCAST_ENV=dev` with sandbox certificates first
4. **Switch to Production**: Update to `TRACKCAST_ENV=prod` with production certificates

The service gracefully handles the transition and will automatically detect when proper configuration is available.