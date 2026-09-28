FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy worker application source code and test suites
COPY worker/ /app/worker/
COPY api/ /app/api/
COPY tests/ /app/tests/
COPY pytest.ini /app/pytest.ini

# Health check checking heartbeat file freshness within 30 seconds
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, time; ts = os.path.getmtime('/tmp/worker_heartbeat') if os.path.exists('/tmp/worker_heartbeat') else 0; exit(0 if (time.time() - ts) < 30 else 1)"

# Command to run worker consumer
CMD ["python", "-m", "worker.src.consumer"]
