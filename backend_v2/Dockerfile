# Build stage - using full Python image for building dependencies
FROM python:3.11 AS builder

WORKDIR /build

# Copy dependency files
COPY pyproject.toml poetry.lock README.md ./

# Install poetry and export dependencies to requirements.txt
RUN pip install --no-cache-dir poetry-plugin-export && \
    pip install --no-cache-dir poetry && \
    poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Runtime stage - using Debian slim for better compatibility with ML libraries
FROM python:3.11-slim AS runtime

# Install runtime dependencies for PostgreSQL and ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 trackrat
WORKDIR /app

# Copy requirements from builder stage
COPY --from=builder /build/requirements.txt .

# Install build dependencies, Python packages, then remove build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        python3-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc g++ libpq-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code, certs, and entrypoint script
COPY src/ ./src/
COPY alembic.ini ./
COPY certs/ ./certs/
COPY docker-entrypoint.sh ./

# Make entrypoint script executable and set ownership
RUN chmod +x docker-entrypoint.sh && \
    chown -R trackrat:trackrat /app

USER trackrat

# Set Python path to include src directory for module imports
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Use entrypoint script that validates APNS before starting
ENTRYPOINT ["./docker-entrypoint.sh"]
