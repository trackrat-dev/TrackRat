# TrackRat Universal Links Deployment

This directory contains everything needed to deploy Universal Links functionality for TrackRat train sharing.

## 📁 Files

- **`apple-app-site-association`** - iOS Universal Links configuration (Team ID: D5RZZ55J9R)
- **`web-fallback.html`** - Fallback web page for users without the app
- **`gcs-simple-setup.tf`** - Terraform configuration for GCS + Load Balancer
- **`deploy-universal-links.sh`** - One-command deployment script
- **`UNIVERSAL_LINKS_SETUP.md`** - Detailed setup documentation
- **`SIMPLE_GCS_SETUP.md`** - Alternative simple GCS-only setup

## 🚀 Quick Deployment

### Prerequisites
- Google Cloud CLI installed and authenticated
- Terraform installed
- TrackRat project ID configured

### Deploy Command
```bash
cd universal-links-deployment
export PROJECT_ID="your-trackrat-project-id"  # Optional if gcloud config is set
./deploy-universal-links.sh
```

### What Gets Created
- **GCS Bucket**: Hosts the Universal Links files
- **Load Balancer**: Routes traffic to the bucket with SSL
- **Static IP**: For pointing your DNS
- **SSL Certificate**: Auto-provisioned for trackrat.net
- **CDN**: Global caching for performance

## 🔗 URL Structure

### Universal Links (Production)
- **AASA**: `https://trackrat.net/.well-known/apple-app-site-association`
- **Train Sharing**: `https://trackrat.net/train/{train_id}?from={code}&to={code}`
- **Example**: `https://trackrat.net/train/NJT-3849?from=NY&to=TR&date=2025-01-14`

### Development/Testing URLs
- **Direct AASA**: `https://storage.googleapis.com/{bucket}/.well-known/apple-app-site-association`
- **Direct Fallback**: `https://storage.googleapis.com/{bucket}/train-fallback.html`

## 🎯 How It Works

1. **iOS App**: Share button generates trackrat.net URLs
2. **Universal Links**: If app installed, opens directly in TrackRat
3. **Web Fallback**: If app not installed, shows train info + App Store link
4. **Auto-detection**: JavaScript attempts to open app, falls back to web page

## 📋 DNS Setup

After deployment, point your DNS A record:
```
trackrat.net        A    [STATIC_IP_FROM_OUTPUT]
www.trackrat.net    A    [STATIC_IP_FROM_OUTPUT]
```

SSL certificate will auto-provision in 5-10 minutes.

## 🧪 Testing

### 1. Validate AASA File
- **Apple's Validator**: https://search.developer.apple.com/appsearch-validation-tool/
- **Enter**: `trackrat.net`

### 2. Test URLs
- **AASA**: `curl -I https://trackrat.net/.well-known/apple-app-site-association`
- **Train Page**: `https://trackrat.net/train/test123?from=NY&to=TR`

### 3. iOS Testing
- **With App**: Tap link in Messages → Opens TrackRat app
- **Without App**: Tap link → Opens web page with App Store link

## 💰 Cost Estimate

- **GCS Storage**: ~$0.02/month (tiny files)
- **Load Balancer**: ~$18/month (standard Google rate)
- **Bandwidth**: ~$0.12/GB (minimal usage)
- **Total**: ~$20/month for enterprise-grade hosting

## 🔄 Updates

To update the files:

1. **Modify files** in this directory
2. **Re-run deployment**: `./deploy-universal-links.sh`
3. **Terraform will update** only changed resources

## 🚨 Troubleshooting

### Universal Links Not Working
1. **Check AASA**: Ensure returns 200 with `application/json`
2. **Verify Team ID**: D5RZZ55J9R in apple-app-site-association
3. **Clear iOS Cache**: Uninstall/reinstall app
4. **Check DNS**: Ensure trackrat.net points to static IP

### Deployment Errors
1. **Missing Terraform**: Install from https://terraform.io
2. **GCP Auth**: Run `gcloud auth application-default login`
3. **Project ID**: Set `export PROJECT_ID=your-project`
4. **Permissions**: Ensure service account has required roles

## 📚 Documentation

- **Full Setup Guide**: `UNIVERSAL_LINKS_SETUP.md`
- **Simple GCS Only**: `SIMPLE_GCS_SETUP.md`
- **iOS Implementation**: `../ios/CLAUDE.md`

## 🎯 Next Steps After Deployment

1. **Point DNS** to the static IP output
2. **Wait for SSL** certificate (5-10 minutes)
3. **Test AASA** validation
4. **Test sharing** from iOS app
5. **Verify Universal Links** work on physical device