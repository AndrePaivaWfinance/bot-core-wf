#!/bin/bash

# Set up development environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Run the application with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload