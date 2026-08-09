#!/bin/bash
# Build and deploy webpage_v2 to Cloudflare Workers Static Assets
#
# Usage: ./scripts/deploy-webpage.sh [staging|production] [--cloudflare-only] [--dry-run]
#
# trackrat.net and www.trackrat.net are served directly by the production
# Worker's custom domains (webpage_v2/wrangler.jsonc), with no GCS fallback —
# so a production run here deploys the LOCAL build straight to the live site.
# A bare `production` run is always refused; --cloudflare-only is the explicit
# acknowledgement. The normal path is pushing to the `production` branch. See
# the guard below.
#
# Defaults to production if no environment specified. The destination Worker
# name and its custom domains come from the matching environment in
# webpage_v2/wrangler.jsonc — there is no override flag, because the whole
# point of keeping them in version control is that a deploy cannot be pointed
# somewhere else from the command line.
#
# Prerequisites: npm, plus CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in
# the environment. The token needs the "Workers Scripts: Edit" account
# permission, and "Workers Routes: Edit" on the trackrat.net zone for the
# custom domains — the same token the Cloud Build triggers read from Secret
# Manager (cloudflare-workers-api-token / cloudflare-account-id).
#
# Cache headers, HSTS and the AASA content type are NOT applied here: they live
# in webpage_v2/public/_headers, which Vite copies into dist/ and Cloudflare
# reads on upload. See issue #1713.

set -e

PROD_API_URL="https://apiv2.trackrat.net/api/v2"
STAGING_API_URL="https://staging-api.trackrat.net/api/v2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/webpage_v2"
DIST_DIR="$WEB_DIR/dist"
DRY_RUN=false
ENVIRONMENT="production"
CLOUDFLARE_ONLY=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --cloudflare-only)
            CLOUDFLARE_ONLY=true
            ;;
        staging)
            ENVIRONMENT="staging"
            ;;
        production)
            ENVIRONMENT="production"
            ;;
        *)
            echo "❌ Unknown argument: $arg"
            echo "Usage: $0 [staging|production] [--cloudflare-only] [--dry-run]"
            exit 1
            ;;
    esac
done

if [[ "$ENVIRONMENT" == "staging" ]]; then
    API_URL="$STAGING_API_URL"
else
    API_URL="$PROD_API_URL"
fi

echo "Environment: $ENVIRONMENT"
echo "API URL: $API_URL"

# trackrat.net and www.trackrat.net are served by the production Worker's
# custom domains (the `routes` in wrangler.jsonc) — the Google load balancer
# that used to serve the apex from GCS was deleted on 2026-08-08, so there is
# no fallback behind the Worker. A production run here therefore ships whatever
# is in this working tree straight to the live site, bypassing CI entirely.
# That is sometimes the right tool (incident response, rolling back to a
# known-good checkout), but it must never happen by accident — so a bare
# `production` run is refused unconditionally, and --cloudflare-only is the
# explicit acknowledgement. The normal path is pushing to the `production`
# branch and letting Cloud Build build from committed source.
if [[ "$ENVIRONMENT" == "production" ]] && ! $CLOUDFLARE_ONLY; then
    echo "❌ Refusing bare 'production': this deploys the LOCAL build directly to the LIVE site trackrat.net."
    echo ""
    echo "   The normal path is pushing to the 'production' branch — Cloud Build builds"
    echo "   from committed source and deploys to the same Worker."
    echo ""
    echo "   To deploy from this machine anyway:  $0 production --cloudflare-only"
    exit 3
fi

# Check prerequisites
if ! command -v npm &>/dev/null; then
    echo "❌ npm not found"
    exit 1
fi

if ! $DRY_RUN; then
    if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
        echo "❌ CLOUDFLARE_API_TOKEN not set."
        echo "   Needs 'Workers Scripts: Edit' (account) and 'Workers Routes: Edit' (trackrat.net zone),"
        echo "   or read the deploy token the pipeline uses:"
        echo "   export CLOUDFLARE_API_TOKEN=\$(gcloud secrets versions access latest \\"
        echo "     --secret=cloudflare-workers-api-token --project=trackrat-v2)"
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
    echo "🔍 Dry run — wrangler will report the asset manifest it would upload:"
    npx wrangler deploy --env "$ENVIRONMENT" --dry-run
else
    echo ""
    echo "🚀 Deploying to Cloudflare Workers ($ENVIRONMENT)..."

    npx wrangler deploy --env "$ENVIRONMENT"

    if [[ "$ENVIRONMENT" == "production" ]]; then
        # The guard above means we only get here with --cloudflare-only. Say
        # what actually changed: the custom domains serve the apex, so this
        # local build IS live now.
        echo "✅ Deploy complete: trackrat.net and www.trackrat.net now serve this local build."
    else
        echo "✅ Deploy complete ($ENVIRONMENT)"
    fi
fi
