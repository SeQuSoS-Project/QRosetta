#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

# Configuration Variables
PROJECT_ID="qrosetta"

echo "========================================"
echo "Deploying Quantum Rosetta Frontend to GCP"
echo "Project ID: $PROJECT_ID"
echo "========================================"

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- 1. Creating Google Cloud Artifact Registry ---"
# Create the repository if it doesn't exist. Ignore error if it does.
gcloud artifacts repositories create rosetta-frontend-repo \
    --repository-format=docker \
    --location=us-central1 \
    --quiet || true

# Define the repository path
REPO="us-central1-docker.pkg.dev/$PROJECT_ID/rosetta-frontend-repo"

echo ""
echo "--- 2. Building Frontend Docker Image ---"
docker build -t "$REPO/rosetta-frontend:latest" -f infra/Dockerfile.frontend .

echo ""
echo "--- 3. Pushing Image to Artifact Registry ---"
docker push "$REPO/rosetta-frontend:latest"

echo ""
echo "--- 4. Deploying to Google Cloud Run ---"
gcloud run deploy rosetta-frontend \
    --image "$REPO/rosetta-frontend:latest" \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080

echo "========================================"
echo "Deployment successfully initiated!"
