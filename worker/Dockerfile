FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install poetry
RUN pip install poetry

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy worker code
COPY worker/ ./worker/

# Set environment variables
ENV PYTHONPATH=/app
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

# Create directory for prometheus metrics
RUN mkdir -p /tmp/prometheus_multiproc

# Expose port
EXPOSE 8771

# Run the worker
CMD ["poetry", "run", "uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8771"] 