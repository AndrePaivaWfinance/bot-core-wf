#!/bin/bash

# Bot Framework Startup Script
echo "Starting Bot Framework..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your configuration before running again."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check if running in Docker
if [ "$DOCKERIZED" = "true" ]; then
    echo "Running in Docker mode..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000
else
    echo "Running in local mode..."
    # Check if virtual environment exists
    if [ ! -d .venv ]; then
        echo "Creating virtual environment..."
        python -m venv .venv
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    # Start the application
    echo "Starting server..."
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi