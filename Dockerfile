FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .


# Create non-root user
RUN useradd -m -u 1000 botuser

# Create cache and templates folders with correct permissions
RUN mkdir -p /app/.cache /app/templates && \
    chown -R botuser:botuser /app/.cache /app/templates

USER botuser

# Expose port
EXPOSE 80

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=80

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]