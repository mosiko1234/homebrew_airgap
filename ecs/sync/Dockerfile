# Multi-stage Dockerfile for ECS Homebrew Bottles Sync Worker
# Build arguments
ARG PYTHON_VERSION=3.11
ARG BUILD_DATE
ARG VCS_REF

# Stage 1: Build dependencies
FROM python:${PYTHON_VERSION}-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements first for better caching
COPY ecs/sync/requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    # Remove unnecessary files to reduce size
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true

# Stage 2: Runtime image
FROM python:${PYTHON_VERSION}-slim as runtime

# Add metadata labels
LABEL org.opencontainers.image.title="Homebrew Sync Worker" \
      org.opencontainers.image.description="ECS worker for syncing Homebrew bottles" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="latest" \
      maintainer="DevOps Team"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy shared modules (with optimization for layer caching)
COPY shared/ ./shared/

# Copy ECS sync application
COPY ecs/sync/main.py ./

# Create working directory for temporary files
RUN mkdir -p /tmp/homebrew-sync

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORK_DIR=/tmp/homebrew-sync \
    LOG_LEVEL=INFO \
    PROGRESS_REPORT_INTERVAL=300

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser && \
    chown -R appuser:appuser /app /tmp/homebrew-sync
USER appuser

# Health check with better error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys, importlib; importlib.import_module('main'); sys.exit(0)" || exit 1

# Run the ECS sync worker
CMD ["python", "main.py"]