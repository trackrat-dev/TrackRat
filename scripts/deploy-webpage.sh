#!/bin/bash
# Build and deploy webpage_v2 to GCS
#
# Usage: ./scripts/deploy-webpage.sh [--dry-run]
#
# Prerequisites: gsutil authenticated, npm installed

set -e

BUCKET="gs://trackrat-links-2caf78c68fded156"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/webpage_v2"
DIST_DIR="$WEB_DIR/dist"
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        *)
            echo "❌ Unknown argument: $arg"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

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
echo "📦 Building webpage_v2..."
cd "$WEB_DIR"
npm ci --silent
npm run build

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

    echo "✅ Deploy complete"
fi
