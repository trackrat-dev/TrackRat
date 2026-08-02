#!/bin/bash
# Build and deploy webpage_v2 to Cloudflare Pages
#
# Usage: ./scripts/deploy-webpage.sh [staging|production] [--project=<name>] [--dry-run]
#
# Defaults to production if no environment specified.
# --project overrides the destination Pages project while keeping the
# environment's API URL. Useful for deploying into a scratch project to
# rehearse a migration without touching the live one.
#
# Prerequisites: npm, plus CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in
# the environment. The token needs the "Cloudflare Pages: Edit" account
# permission — the same token the Cloud Build triggers read from Secret
# Manager (cloudflare-pages-api-token / cloudflare-account-id).
#
# Cache headers, HSTS and the AASA content type are NOT applied here: they live
# in webpage_v2/public/_headers, which Vite copies into dist/ and Cloudflare
# reads on upload. See issue #1713.

set -e

PROD_PROJECT="trackrat-webpage-production"
STAGING_PROJECT="trackrat-webpage-staging"
PROD_API_URL="https://apiv2.trackrat.net/api/v2"
STAGING_API_URL="https://staging-api.trackrat.net/api/v2"

# Each Pages project has a production branch fixed at creation. A deploy whose
# --branch does not match it is filed as a PREVIEW deployment: it succeeds, and
# the custom domain keeps serving the previous release.
PROD_BRANCH="production"
STAGING_BRANCH="main"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/webpage_v2"
DIST_DIR="$WEB_DIR/dist"
DRY_RUN=false
ENVIRONMENT="production"
PROJECT_OVERRIDE=""

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --project=*)
            PROJECT_OVERRIDE="${arg#--project=}"
            ;;
        staging)
            ENVIRONMENT="staging"
            ;;
        production)
            ENVIRONMENT="production"
            ;;
        *)
            echo "❌ Unknown argument: $arg"
            echo "Usage: $0 [staging|production] [--project=<name>] [--dry-run]"
            exit 1
            ;;
    esac
done

if [[ "$ENVIRONMENT" == "staging" ]]; then
    PAGES_PROJECT="$STAGING_PROJECT"
    PAGES_BRANCH="$STAGING_BRANCH"
    API_URL="$STAGING_API_URL"
else
    PAGES_PROJECT="$PROD_PROJECT"
    PAGES_BRANCH="$PROD_BRANCH"
    API_URL="$PROD_API_URL"
fi

if [[ -n "$PROJECT_OVERRIDE" ]]; then
    PAGES_PROJECT="$PROJECT_OVERRIDE"
fi

echo "Environment: $ENVIRONMENT"
echo "Pages project: $PAGES_PROJECT"
echo "Deploy branch: $PAGES_BRANCH"
echo "API URL: $API_URL"

# Check prerequisites
if ! command -v npm &>/dev/null; then
    echo "❌ npm not found"
    exit 1
fi

if ! $DRY_RUN; then
    if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
        echo "❌ CLOUDFLARE_API_TOKEN not set."
        echo "   Create a token with the 'Cloudflare Pages: Edit' account permission, or read the"
        echo "   deploy token the pipeline uses:"
        echo "   export CLOUDFLARE_API_TOKEN=\$(gcloud secrets versions access latest \\"
        echo "     --secret=cloudflare-pages-api-token --project=trackrat-v2)"
        exit 1
    fi
    if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
        echo "❌ CLOUDFLARE_ACCOUNT_ID not set."
        echo "   export CLOUDFLARE_ACCOUNT_ID=\$(gcloud secrets versions access latest \\"
        echo "     --secret=cloudflare-account-id --project=trackrat-v2)"
        exit 1
    fi
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

# The serving policy is a build artifact now, so a missing _headers is a broken
# deploy (no HSTS, no immutable asset caching, AASA served as the wrong type)
# that looks entirely successful. Fail before uploading instead.
if [[ ! -f "$DIST_DIR/_headers" ]]; then
    echo "❌ dist/_headers is missing — webpage_v2/public/_headers did not make it into the build."
    exit 1
fi

# Deploy
if $DRY_RUN; then
    echo ""
    echo "🔍 Dry run — would deploy $FILE_COUNT files to Pages project '$PAGES_PROJECT' (branch $PAGES_BRANCH):"
    find "$DIST_DIR" -type f -printf '  %P\n' | sort
else
    echo ""
    echo "🚀 Deploying to Cloudflare Pages project '$PAGES_PROJECT'..."

    npx wrangler pages deploy "$DIST_DIR" \
        --project-name="$PAGES_PROJECT" \
        --branch="$PAGES_BRANCH" \
        --commit-dirty=true

    echo "✅ Deploy complete ($ENVIRONMENT)"
fi
