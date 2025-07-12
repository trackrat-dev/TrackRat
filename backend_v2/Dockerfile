# Build stage - using full Python image for building dependencies
FROM python:3.11 AS builder

WORKDIR /build

# Copy dependency files
COPY pyproject.toml poetry.lock README.md ./

# Install poetry and export dependencies to requirements.txt
RUN pip install --no-cache-dir poetry-plugin-export && \
    pip install --no-cache-dir poetry && \
    poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Runtime stage - using Alpine for smallest size
FROM python:3.11-alpine AS runtime

# Install runtime dependencies for PostgreSQL
RUN apk add --no-cache \
    postgresql-libs \
    libstdc++

# Create non-root user
RUN adduser -D -u 1000 trackrat
WORKDIR /app

# Copy requirements from builder stage
COPY --from=builder /build/requirements.txt .

# Install build dependencies, Python packages, then remove build deps
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        postgresql-dev \
        python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del .build-deps

# Copy application code
COPY src/ ./src/
COPY alembic.ini ./

# Set ownership
RUN chown -R trackrat:trackrat /app

USER trackrat

# Set Python path to include src directory for module imports
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Run migrations and start app
CMD ["sh", "-c", "alembic upgrade head && uvicorn trackrat.main:app --host 0.0.0.0 --port 8000"]