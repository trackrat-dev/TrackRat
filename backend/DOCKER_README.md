# TrackCast Inference Service - Docker Setup

This document explains how to build and run the TrackCast inference service using Docker.

## Architecture Overview

The containerized service includes:
- **FastAPI API server** for train predictions
- **Data collection services** from NJ Transit and Amtrak APIs
- **Prediction engine** using pre-trained ML models
- **Health check endpoints** for container orchestration

## Model Separation

This container implements **inference-only** functionality:
- ✅ Model loading and prediction
- ✅ API serving and data collection
- ✅ Feature engineering for inference
- ❌ Model training (handled separately)
- ❌ Visualization tools
- ❌ Development/testing tools

## Quick Start

### 1. Build the Docker Image

```bash
# From the backend directory
cd /Users/andy/projects/TrackRat/backend

# Build the inference service image
docker build -t trackcast-inference:latest .
```

### 2. Prepare Model Files

The container expects model files to be mounted externally:

```bash
# Create a local models directory
mkdir -p ./models-volume

# Copy your trained models to this directory
# Example structure:
# ./models-volume/
#   ├── track_pred_model_1.0.0_NY_20250531101111.pt
#   ├── scaler_1.0.0_NY_20250531101111.pkl
#   ├── encoders_1.0.0_NY_20250531101111.pkl
#   └── ...
```

### 3. Run the Container

```bash
# Run with external model mount and database connection
docker run -d \
  --name trackcast-inference \
  -p 8000:8000 \
  -v $(pwd)/models-volume:/app/models \
  -e DATABASE_URL="postgresql://user:password@host:5432/trackcast" \
  -e MODEL_PATH="/app/models" \
  -e TRACKCAST_ENV="dev" \
  -e NJT_USERNAME="your_nj_transit_username" \
  -e NJT_PASSWORD="your_nj_transit_password" \
  trackcast-inference:latest
```

### 4. Verify the Service

```bash
# Check health status
curl http://localhost:8000/health

# Test API endpoints
curl http://localhost:8000/api/trains/

# View logs
docker logs trackcast-inference
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | - |
| `MODEL_PATH` | Directory containing model files | No | `/app/models` |
| `TRACKCAST_ENV` | Environment (dev/staging/prod) | No | `prod` |
| `NJT_USERNAME` | NJ Transit API username | Yes | - |
| `NJT_PASSWORD` | NJ Transit API password | Yes | - |

## Volume Mounts

- `/app/models` - Mount directory containing pre-trained model files
- `/app/config` - Optional: Mount custom configuration files
- `/app/logs` - Optional: Mount for persistent log storage

## Health Checks

The container includes comprehensive health checks:
- `/health` - Detailed health status including database and model availability
- Docker `HEALTHCHECK` - Automated container health monitoring

## Development vs Production

### Development
```bash
# Mount source code for development
docker run -it --rm \
  -p 8000:8000 \
  -v $(pwd):/app \
  -v $(pwd)/models-volume:/app/models \
  -e DATABASE_URL="postgresql://localhost:5432/trackcast_dev" \
  trackcast-inference:latest \
  uvicorn trackcast.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Production
```bash
# Use with external orchestration (Kubernetes, Cloud Run, etc.)
docker run -d \
  -p 8000:8000 \
  -v /path/to/production/models:/app/models \
  -e DATABASE_URL="$DATABASE_URL" \
  --restart unless-stopped \
  trackcast-inference:latest
```

## Cloud Build

Build and push to Google Artifact Registry:

```bash
# Submit build to Cloud Build
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _ENV=dev,_REGION=us-central1

# For different environments
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _ENV=staging,_REGION=us-central1
```

## Troubleshooting

### Common Issues

1. **Models not found**
   ```bash
   # Check model mount
   docker exec trackcast-inference ls -la /app/models
   ```

2. **Database connection failed**
   ```bash
   # Check DATABASE_URL format
   # postgresql://user:password@host:5432/database
   ```

3. **API credentials missing**
   ```bash
   # Ensure NJT_USERNAME and NJT_PASSWORD are set
   docker exec trackcast-inference env | grep NJT
   ```

### Logs

```bash
# View application logs
docker logs trackcast-inference

# Follow logs in real-time
docker logs -f trackcast-inference

# Get health check details
curl http://localhost:8000/health | jq .
```

## Security Notes

- Container runs as non-root user `trackcast`
- Models mounted as external volumes (not in image)
- Sensitive credentials via environment variables only
- Minimal attack surface (no training tools)

## Image Size

The inference-only image is optimized for size:
- Multi-stage build removes build dependencies
- Excludes training/visualization libraries
- Typical size: ~500MB (vs 1.5GB+ with training tools)