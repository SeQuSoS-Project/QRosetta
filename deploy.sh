#!/bin/bash
set -e # Exit immediately if a command fails

PROJECT_ID="qrosetta"
REGION="us-central1"
REPO="us-central1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy"

# Cloud-Specific Safeguards
CLOUD_TIMEOUT="300s"
CLOUD_MAX_QUBITS="10"

echo "==================================================="
echo "   Quantum Rosetta - Local Cache Deployer"
echo "==================================================="

# 1. Define Runners
RUNNERS=(
    "pytket-qiskit-runner"
    "pytket-cirq-runner"
    "pytket-qulacs-runner"
    "pytket-braket-runner"
    "pytket-projectq-runner"
    "pytket-quest-runner"
    "pennylane-lightning-runner"
    "pennylane-default-runner"
)

# 2. Build, Push, and Deploy Runners
declare -A RUNNER_URLS

for RUNNER in "${RUNNERS[@]}"; do
    echo "---------------------------------------------------"
    echo "Processing $RUNNER..."
    IMAGE_URL="$REPO/$RUNNER:latest"

    # Local Build (uses cache)
    echo "Building locally..."
    docker build -t $IMAGE_URL -f ./$RUNNER/Dockerfile .

    # Push to Registry
    echo "Pushing to Artifact Registry..."
    docker push $IMAGE_URL

    # Deploy Pre-Built Image
    echo "Deploying to Cloud Run..."
    URL=$(gcloud run deploy $RUNNER \
        --image $IMAGE_URL \
        --ingress internal \
        --allow-unauthenticated \
        --region $REGION \
        --memory 512Mi \
        --cpu 1 \
        --timeout $CLOUD_TIMEOUT \
        --set-env-vars "MAX_QUBITS=$CLOUD_MAX_QUBITS" \
        --max-instances 3 \
        --format 'value(status.url)' \
        --quiet)
    
    RUNNER_URLS[$RUNNER]=$URL
    echo "Deployed $RUNNER at $URL"
done

echo "==================================================="
echo "Runners deployed. Deploying API Gateway..."
echo "==================================================="

# 3. Prepare API Environment Variables mapping to the new secure runner URLs
API_ENV_VARS="MAX_QUBITS=$CLOUD_MAX_QUBITS,STORAGE_MODE=memory"
API_ENV_VARS+=",PYTKET_QISKIT_RUNNER_URL=${RUNNER_URLS['pytket-qiskit-runner']}"
API_ENV_VARS+=",PYTKET_CIRQ_RUNNER_URL=${RUNNER_URLS['pytket-cirq-runner']}"
API_ENV_VARS+=",PYTKET_QULACS_RUNNER_URL=${RUNNER_URLS['pytket-qulacs-runner']}"
API_ENV_VARS+=",PYTKET_BRAKET_RUNNER_URL=${RUNNER_URLS['pytket-braket-runner']}"
API_ENV_VARS+=",PYTKET_PROJECTQ_RUNNER_URL=${RUNNER_URLS['pytket-projectq-runner']}"
API_ENV_VARS+=",PYTKET_QUEST_RUNNER_URL=${RUNNER_URLS['pytket-quest-runner']}"
API_ENV_VARS+=",PENNYLANE_LIGHTNING_RUNNER_URL=${RUNNER_URLS['pennylane-lightning-runner']}"
API_ENV_VARS+=",PENNYLANE_DEFAULT_RUNNER_URL=${RUNNER_URLS['pennylane-default-runner']}"

# 4. Build, Push, and Deploy API
API_IMAGE_URL="$REPO/rosetta-api:latest"
echo "Building API locally..."
docker build -t $API_IMAGE_URL -f ./rosetta-api/Dockerfile .

echo "Pushing API to Artifact Registry..."
docker push $API_IMAGE_URL

echo "Deploying API to Cloud Run..."
API_PUBLIC_URL=$(gcloud run deploy "rosetta-api" \
    --image $API_IMAGE_URL \
    --region $REGION \
    --allow-unauthenticated \
    --ingress all \
    --network default \
    --vpc-egress all-traffic \
    --memory 512Mi \
    --cpu 1 \
    --timeout $CLOUD_TIMEOUT \
    --set-env-vars "$API_ENV_VARS" \
    --max-instances 3 \
    --format 'value(status.url)' \
    --quiet)

echo "==================================================="
echo "Deployment Complete!"
echo "Public API URL: $API_PUBLIC_URL"
echo "==================================================="