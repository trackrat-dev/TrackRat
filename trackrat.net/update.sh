#!/bin/bash
#

set -xe

BUCKET="gs://trackrat-links-2caf78c68fded156"

# Landing page
gsutil cp ./index.html "$BUCKET/index.html"
gsutil cp ./icon.png "$BUCKET/icon.png"
gsutil cp ./privacy.txt "$BUCKET/privacy.txt"

# Screenshots (if they exist)
[ -f ./screenshot-home.png ] && gsutil cp ./screenshot-home.png "$BUCKET/screenshot-home.png"
[ -f ./screenshot-details.png ] && gsutil cp ./screenshot-details.png "$BUCKET/screenshot-details.png"

# Deep link fallback
gsutil cp ./train-fallback.html "$BUCKET/train-fallback.html"

echo "Deployed to $BUCKET"
