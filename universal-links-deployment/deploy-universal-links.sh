#!/bin/bash

# Deploy Universal Links to GCS + Load Balancer
# Run this from the universal-links-deployment directory

set -e

echo "🚀 Deploying TrackRat Universal Links to GCS..."

# Check if required files exist
if [[ ! -f "apple-app-site-association" ]]; then
    echo "❌ apple-app-site-association file not found"
    exit 1
fi

if [[ ! -f "web-fallback.html" ]]; then
    echo "❌ web-fallback.html file not found"
    exit 1
fi

if [[ ! -f "gcs-simple-setup.tf" ]]; then
    echo "❌ gcs-simple-setup.tf file not found"
    exit 1
fi

# Get project ID
if [[ -z "$PROJECT_ID" ]]; then
    echo "📋 Getting current project ID..."
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [[ -z "$PROJECT_ID" ]]; then
        echo "❌ No project ID found. Set with: export PROJECT_ID=your-project-id"
        exit 1
    fi
fi

echo "📋 Using project: $PROJECT_ID"

# Deploy Terraform if available
if command -v terraform &> /dev/null; then
    echo "🏗️  Deploying infrastructure with Terraform..."
    
    # Initialize Terraform
    terraform init
    
    # Plan deployment
    echo "🏗️  Planning deployment..."
    terraform plan -var="project_id=$PROJECT_ID"
    
    # Apply deployment
    echo "🏗️  Applying deployment..."
    terraform apply -auto-approve -var="project_id=$PROJECT_ID"
    
    # Get outputs
    echo ""
    echo "✅ Deployment complete!"
    echo ""
    
    STATIC_IP=$(terraform output -raw static_ip 2>/dev/null || echo "Not available")
    BUCKET_NAME=$(terraform output -raw bucket_name 2>/dev/null || echo "Not available")
    
    echo "🌍 Static IP: $STATIC_IP"
    echo "🪣 Bucket: $BUCKET_NAME"
    echo ""
    echo "🔧 DNS Setup:"
    echo "   Point trackrat.net A record to: $STATIC_IP"
    echo ""
    echo "🔗 Test URLs (immediate):"
    if [[ "$BUCKET_NAME" != "Not available" ]]; then
        echo "   AASA: https://storage.googleapis.com/$BUCKET_NAME/.well-known/apple-app-site-association"
        echo "   Fallback: https://storage.googleapis.com/$BUCKET_NAME/train-fallback.html"
    fi
    echo ""
    echo "🔗 Production URLs (after DNS):"
    echo "   AASA: https://trackrat.net/.well-known/apple-app-site-association"
    echo "   Train: https://trackrat.net/train/test123?from=NY&to=TR"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Point DNS A record to static IP above"
    echo "   2. Wait 5-10 minutes for SSL certificate"
    echo "   3. Test the production URLs"
    echo "   4. Test Universal Links on iOS device"
    
else
    echo "❌ Terraform not found. Please install Terraform to deploy infrastructure."
    echo "💡 Alternative: Use the manual GCS setup in SIMPLE_GCS_SETUP.md"
    exit 1
fi
