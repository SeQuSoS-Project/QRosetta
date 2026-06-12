#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

if [ -f .env ]; then
    echo ">> Loading variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo ">> WARNING: .env file not found. Falling back to system environment variables."
fi

# Configuration Variables
PROJECT_ID="${GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"

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
    --location="${REGION}" \
    --quiet || true

# Define the repository path
REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/rosetta-frontend-repo"

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
    --region "${REGION}" \
    --allow-unauthenticated \
    --port 8080

echo "========================================"
echo "Deployment successfully initiated!"
