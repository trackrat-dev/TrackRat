# TrackCast Inference Service Dockerfile
# Multi-stage build for optimal image size and security

# Stage 1: Dependencies builder
FROM python:3.11-slim AS builder

# Set environment variables for minimal installs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies (CPU-only for container optimization)
COPY requirements-production.txt .
# Install all dependencies with CPU-only PyTorch pinned in requirements (~2GB savings)
RUN pip install --no-cache-dir -r requirements-production.txt \
    && find /opt/venv -type f -name "*.pyc" -delete \
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Stage 2: Production runtime
FROM python:3.11-slim AS runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    MODEL_PATH="/app/models" \
    TRACKCAST_ENV="dev" \
    DEBIAN_FRONTEND=noninteractive \
    OTEL_SAMPLE_RATE="0.1" \
    OTEL_SERVICE_NAME="trackcast-api" \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED="true"

# Install runtime system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash trackcast \
    && mkdir -p /app /app/models /app/config /app/logs \
    && chown -R trackcast:trackcast /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=trackcast:trackcast trackcast/ ./trackcast/
COPY --chown=trackcast:trackcast pyproject.toml ./
COPY --chown=trackcast:trackcast config/ ./config/
COPY --chown=trackcast:trackcast models/ ./models/

# Copy entrypoint script
COPY --chown=trackcast:trackcast entrypoint.sh ./entrypoint.sh

# Install the package in development mode for CLI access
RUN pip install -e . \
    && find /opt/venv -type f -name "*.pyc" -delete \
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Make entrypoint script executable
RUN chmod +x ./entrypoint.sh

# Switch to non-root user
USER trackcast

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint to run migrations before starting the app
ENTRYPOINT ["./entrypoint.sh"]

# Default command - can be overridden
CMD ["gunicorn", "trackcast.api.app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
