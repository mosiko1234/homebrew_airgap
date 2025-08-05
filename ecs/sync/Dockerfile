# Dockerfile for ECS Homebrew Bottles Sync Worker
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ecs/sync/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared/ ./shared/

# Copy ECS sync application
COPY ecs/sync/main.py ./

# Create working directory for temporary files
RUN mkdir -p /tmp/homebrew-sync

# Set environment variables
ENV PYTHONPATH=/app
ENV WORK_DIR=/tmp/homebrew-sync
ENV LOG_LEVEL=INFO
ENV PROGRESS_REPORT_INTERVAL=300

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app /tmp/homebrew-sync
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the ECS sync worker
CMD ["python", "main.py"]