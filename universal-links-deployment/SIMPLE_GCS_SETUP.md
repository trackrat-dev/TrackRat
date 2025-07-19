# Simple GCS Setup for Universal Links

If you want to quickly test the Universal Links functionality without the full Load Balancer setup, here's a simplified approach:

## 🚀 Quick Setup (5 minutes)

### Step 1: Create GCS Bucket
```bash
# Set your project ID
export PROJECT_ID="your-trackrat-project-id"

# Create bucket with unique name
BUCKET_NAME="trackrat-links-$(openssl rand -hex 4)"
gsutil mb -p $PROJECT_ID gs://$BUCKET_NAME

# Make it publicly readable
gsutil iam ch allUsers:objectViewer gs://$BUCKET_NAME
```

### Step 2: Upload Files
```bash
# Upload AASA file
gsutil -h "Content-Type:application/json" \
       cp apple-app-site-association \
       gs://$BUCKET_NAME/.well-known/apple-app-site-association

# Upload fallback page
gsutil -h "Content-Type:text/html" \
       cp web-fallback.html \
       gs://$BUCKET_NAME/train-fallback.html
```

### Step 3: Enable Website Hosting
```bash
# Enable static website hosting
gsutil web set -m train-fallback.html -e train-fallback.html gs://$BUCKET_NAME
```

### Step 4: Test
```bash
# Get the bucket's public URL
echo "AASA URL: https://storage.googleapis.com/$BUCKET_NAME/.well-known/apple-app-site-association"
echo "Train URL: https://storage.googleapis.com/$BUCKET_NAME/train-fallback.html"
```

## ⚠️ Limitations of Simple Setup

1. **URLs won't be clean** - they'll be `storage.googleapis.com/bucket-name/...`
2. **No custom domain** - won't work for Universal Links (needs trackrat.net)
3. **No URL rewriting** - can't handle `/train/{id}` routing automatically

## 🎯 For Production: Use the Full Setup

For actual Universal Links to work, you need:
- Custom domain (trackrat.net)
- Clean URLs (`/train/123` not `/train-fallback.html`)
- HTTPS with proper certificates

This requires the Load Balancer approach in the main proposal.

## 🔄 Migration Path

1. **Start simple** - test the files work with GCS URLs
2. **Verify AASA format** - check Apple's validator
3. **Deploy full setup** - when ready for production Universal Links

The simple setup is perfect for:
- Testing the AASA file format
- Verifying the fallback page works
- Development and debugging

The full setup is required for:
- Production Universal Links
- Clean trackrat.net URLs
- iOS app integration