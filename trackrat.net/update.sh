#!/bin/bash
#

set -xe

BUCKET="gs://trackrat-links-2caf78c68fded156"

# Landing page
gsutil cp ./index.html "$BUCKET/index.html"
gsutil cp ./icon.png "$BUCKET/icon.png"
gsutil cp ./privacy.txt "$BUCKET/privacy.txt"

# Landing page images
gsutil cp ./images/*.png "$BUCKET/images/"

# Deep link fallback
gsutil cp ./train-fallback.html "$BUCKET/train-fallback.html"

echo "Deployed to $BUCKET"
