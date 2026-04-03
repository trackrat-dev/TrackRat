#!/bin/bash
# Build and deploy webpage_v2 to GCS
#
# Usage: ./scripts/deploy-webpage.sh [staging|production] [--dry-run]
#
# Defaults to production if no environment specified.
# Prerequisites: gsutil authenticated, npm installed

set -e

PROD_BUCKET="gs://trackrat-links-2caf78c68fded156"
STAGING_BUCKET="gs://trackrat-webpage-staging"
PROD_API_URL="https://apiv2.trackrat.net/api/v2"
STAGING_API_URL="https://staging.apiv2.trackrat.net/api/v2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/webpage_v2"
DIST_DIR="$WEB_DIR/dist"
DRY_RUN=false
ENVIRONMENT="production"

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        staging)
            ENVIRONMENT="staging"
            ;;
        production)
            ENVIRONMENT="production"
            ;;
        *)
            echo "❌ Unknown argument: $arg"
            echo "Usage: $0 [staging|production] [--dry-run]"
            exit 1
            ;;
    esac
done

if [[ "$ENVIRONMENT" == "staging" ]]; then
    BUCKET="$STAGING_BUCKET"
    API_URL="$STAGING_API_URL"
else
    BUCKET="$PROD_BUCKET"
    API_URL="$PROD_API_URL"
fi

echo "Environment: $ENVIRONMENT"
echo "Bucket: $BUCKET"
echo "API URL: $API_URL"

# Check prerequisites
if ! command -v gsutil &>/dev/null; then
    echo "❌ gsutil not found. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v npm &>/dev/null; then
    echo "❌ npm not found"
    exit 1
fi

# Build
echo "📦 Building webpage_v2 ($ENVIRONMENT)..."
cd "$WEB_DIR"
npm ci --silent
VITE_API_BASE_URL="$API_URL" npm run build

if [[ ! -d "$DIST_DIR" ]]; then
    echo "❌ Build failed: dist/ directory not created"
    exit 1
fi

FILE_COUNT=$(find "$DIST_DIR" -type f | wc -l | tr -d ' ')
echo "✅ Build complete: $FILE_COUNT files in dist/"

# Deploy
if $DRY_RUN; then
    echo ""
    echo "🔍 Dry run — files that would be synced:"
    gsutil -m rsync -r -d -n "$DIST_DIR" "$BUCKET"
else
    echo ""
    echo "🚀 Deploying to $BUCKET..."

    # Sync all files
    gsutil -m rsync -r -d "$DIST_DIR" "$BUCKET"

    # Set cache headers: no-cache on index.html and SW, long cache on hashed assets
    gsutil setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" "$BUCKET/index.html"
    gsutil setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" "$BUCKET/sw.js" 2>/dev/null || true
    gsutil setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" "$BUCKET/registerSW.js" 2>/dev/null || true
    gsutil -m setmeta -h "Cache-Control:public, max-age=31536000, immutable" "$BUCKET/assets/**" 2>/dev/null || true

    # Apple App Site Association must be served as application/json (no file extension)
    gsutil setmeta -h "Content-Type:application/json" "$BUCKET/.well-known/apple-app-site-association" 2>/dev/null || true

    echo "✅ Deploy complete ($ENVIRONMENT)"
fi
