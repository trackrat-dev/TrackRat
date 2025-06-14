# TrackCast Inference Service - Deployment Guide

This guide covers deploying the containerized TrackCast inference service across different environments.

## Overview

The TrackCast inference service has been containerized with the following characteristics:

- **Inference-only**: Separated from training pipeline for lean deployment
- **External models**: Models mounted as volumes, not baked into images
- **Multi-stage build**: Optimized for production deployment
- **Health checks**: Comprehensive monitoring and readiness probes
- **Security**: Non-root user, minimal attack surface

## Deployment Options

### 1. Local Development (Docker Compose)

```bash
# Clone and setup
cd /Users/andy/projects/TrackRat/backend

# Copy environment file and configure
cp .env.example .env
# Edit .env with your NJ Transit credentials

# Create models directory
mkdir -p models-volume
# Copy your trained model files to models-volume/

# Start services
docker-compose up -d

# Check status
docker-compose ps
curl http://localhost:8000/health
```

**Services included:**
- TrackCast inference API (port 8000)
- PostgreSQL database (port 5432)
- Optional pgAdmin (port 8080, use `--profile tools`)

### 2. Google Cloud Run

Cloud Run is ideal for the inference service due to its serverless scaling.

```bash
# Build and push to Artifact Registry
gcloud builds submit --config cloudbuild.yaml --substitutions _ENV=prod

# Deploy to Cloud Run
gcloud run deploy trackcast-inference \
  --image us-central1-docker.pkg.dev/PROJECT_ID/trackcast-inference-prod/trackcast-inference:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars TRACKCAST_ENV=prod,MODEL_PATH=/app/models \
  --set-secrets DATABASE_URL=DATABASE_URL:latest,NJT_USERNAME=NJT_USERNAME:latest,NJT_PASSWORD=NJT_PASSWORD:latest
```

**Model mounting for Cloud Run:**
Since Cloud Run doesn't support volume mounts, consider:
1. **Cloud Storage FUSE**: Mount GCS bucket as filesystem
2. **Init container**: Download models at startup
3. **Larger image**: Include models in image for faster startup

### 3. Google Kubernetes Engine (GKE)

For more control and volume mounting capabilities:

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trackcast-inference
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trackcast-inference
  template:
    metadata:
      labels:
        app: trackcast-inference
    spec:
      containers:
      - name: trackcast-inference
        image: us-central1-docker.pkg.dev/PROJECT_ID/trackcast-inference-prod/trackcast-inference:latest
        ports:
        - containerPort: 8000
        env:
        - name: TRACKCAST_ENV
          value: "prod"
        - name: MODEL_PATH
          value: "/app/models"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: trackcast-secrets
              key: database-url
        volumeMounts:
        - name: models-volume
          mountPath: /app/models
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: models-volume
        gcePersistentDisk:
          pdName: trackcast-models-disk
          fsType: ext4
          readOnly: true
```

### 4. Other Container Platforms

The Docker image is compatible with:
- **AWS ECS/Fargate**: Use task definitions with volume mounts
- **Azure Container Instances**: Mount Azure Files for models
- **DigitalOcean App Platform**: Deploy from container registry
- **Railway/Render**: Simple container deployment

## Infrastructure Setup

### 1. Terraform Deployment

```bash
cd /Users/andy/projects/TrackRat/infra/environments/prod

# Initialize Terraform
terraform init

# Copy and configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit with your project ID and settings

# Create Artifact Registry
terraform plan
terraform apply

# Note the output repository URL
terraform output
```

### 2. Cloud Build Setup

```bash
# Create build triggers for automatic builds
gcloud builds triggers create github \
  --repo-name="TrackRat" \
  --repo-owner="your-github-username" \
  --branch-pattern="^main$" \
  --build-config="backend/cloudbuild.yaml" \
  --substitutions="_ENV=prod,_REGION=us-central1"

# Manual build
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _ENV=prod
```

## Model Management

### Model Storage Options

1. **Google Cloud Storage**
   ```bash
   # Upload models to GCS
   gsutil -m cp models/* gs://your-models-bucket/v1.0.0/
   
   # Download in init container or startup script
   gsutil -m cp -r gs://your-models-bucket/v1.0.0/* /app/models/
   ```

2. **Persistent Volumes** (GKE)
   ```yaml
   apiVersion: v1
   kind: PersistentVolume
   metadata:
     name: trackcast-models-pv
   spec:
     capacity:
       storage: 10Gi
     accessModes:
       - ReadOnlyMany
     gcePersistentDisk:
       pdName: trackcast-models-disk
   ```

3. **Container Images** (for smaller models)
   ```dockerfile
   # Create model-only image
   FROM alpine:latest
   COPY models/ /models/
   VOLUME ["/models"]
   ```

### Model Updates

```bash
# Update models without rebuilding application
# 1. Upload new models to storage
# 2. Update volume/mount point
# 3. Restart containers to reload models

# For Cloud Run: redeploy with new environment variable
gcloud run services update trackcast-inference \
  --update-env-vars MODEL_VERSION=v1.1.0
```

## Monitoring and Observability

### Health Checks

The service provides comprehensive health checks:

```bash
# Basic health check
curl https://your-service-url/health

# Detailed response includes:
{
  "status": "healthy",
  "timestamp": 1703123456.789,
  "checks": {
    "database": {"status": "healthy", "message": "..."},
    "models": {"status": "healthy", "message": "Found 7 model files"},
    "environment": {"status": "healthy", "message": "..."}
  }
}
```

### Logging

Configure structured logging for better observability:

```yaml
# For GKE/Cloud Run
env:
- name: GOOGLE_CLOUD_PROJECT
  value: "your-project-id"
- name: LOG_LEVEL
  value: "INFO"
```

### Metrics

Consider adding monitoring:
- **Cloud Monitoring**: For GCP deployments
- **Prometheus**: For Kubernetes
- **Application metrics**: Request latency, prediction accuracy
- **Business metrics**: Train tracking accuracy, API response times

## Security Considerations

### 1. Container Security
- ✅ Non-root user (`trackcast`)
- ✅ Minimal base image (`python:3.11-slim`)
- ✅ No training tools (reduced attack surface)
- ✅ Read-only model mounts
- ✅ Secrets via environment variables/secret managers

### 2. Network Security
```yaml
# Example network policy for GKE
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: trackcast-netpol
spec:
  podSelector:
    matchLabels:
      app: trackcast-inference
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx-ingress
    ports:
    - protocol: TCP
      port: 8000
```

### 3. Secret Management
```bash
# Store secrets in Google Secret Manager
gcloud secrets create NJT_USERNAME --data-file=nj_username.txt
gcloud secrets create NJT_PASSWORD --data-file=nj_password.txt
gcloud secrets create DATABASE_URL --data-file=db_url.txt

# Grant access to service accounts
gcloud secrets add-iam-policy-binding NJT_USERNAME \
  --member="serviceAccount:your-service-account@project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Troubleshooting

### Common Issues

1. **Models not loading**
   ```bash
   # Check model mount
   kubectl exec -it pod-name -- ls -la /app/models
   
   # Check health endpoint
   curl https://service-url/health | jq '.checks.models'
   ```

2. **Database connection issues**
   ```bash
   # Test database connectivity
   kubectl exec -it pod-name -- python -c "
   import os
   from sqlalchemy import create_engine
   engine = create_engine(os.getenv('DATABASE_URL'))
   print(engine.execute('SELECT 1').scalar())
   "
   ```

3. **API credential issues**
   ```bash
   # Check environment variables
   kubectl exec -it pod-name -- env | grep NJT
   ```

### Performance Tuning

1. **Resource allocation**
   ```yaml
   resources:
     requests:
       memory: "1Gi"
       cpu: "500m"
     limits:
       memory: "2Gi"
       cpu: "1"
   ```

2. **Scaling configuration**
   ```yaml
   # Horizontal Pod Autoscaler
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: trackcast-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: trackcast-inference
     minReplicas: 2
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
   ```

## Cost Optimization

1. **Use spot instances** for non-critical workloads
2. **Implement request-based scaling** for Cloud Run
3. **Use preemptible nodes** for GKE development clusters
4. **Optimize resource requests** based on actual usage
5. **Implement caching** for model predictions

## Next Steps

1. **Set up CI/CD pipeline** with automated testing
2. **Implement blue/green deployments** for zero-downtime updates
3. **Add model versioning** and A/B testing capabilities
4. **Set up alerting** for service health and performance
5. **Implement backup and disaster recovery** procedures