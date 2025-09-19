# Multi-platform Dockerfile
# Para Mac M1/M2 (local): docker build -t mesh:local .
# Para Azure (deploy): docker buildx build --platform linux/amd64 -t mesh:azure .

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories with proper permissions
RUN mkdir -p /app/.cache /app/templates/reports /app/logs /tmp/app && \
    chmod -R 755 /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV BOT_ENV=production
ENV PYTHONDONTWRITEBYTECODE=1

# Azure App Service specific
ENV WEBSITES_PORT=8000
ENV SCM_DO_BUILD_DURING_DEPLOYMENT=false

# Expose port
EXPOSE 8000

# Health check using curl (more reliable)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run as root for Azure App Service compatibility
# Azure App Service handles security at the platform level
USER root

# Start the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]