#!/bin/bash

# Build and run Docker container
docker build -t bot-framework .
docker run -p 8000:8000 --env-file .env bot-framework