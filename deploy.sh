#!/bin/bash

# Configuration
REGION="us-central1"
# PROJECT_ID is automatically picked up from gcloud config, or you can set it here.

echo "==================================================="
echo "   Quantum Rosetta - Google Cloud Run Deployer"
echo "==================================================="

# List of runners to deploy (Service Name : Directory)
# We use an associative array or just parallel lists. Simple loop is better for portability.
RUNNERS=(
    "pytket-qiskit-runner:pytket-qiskit-runner"
    "pytket-cirq-runner:pytket-cirq-runner"
    "pytket-qulacs-runner:pytket-qulacs-runner"
    "pytket-braket-runner:pytket-braket-runner"
    "pytket-projectq-runner:pytket-projectq-runner"
    "pytket-quest-runner:pytket-quest-runner"
    "pennylane-lightning-runner:pennylane-lightning-runner"
    "pennylane-default-runner:pennylane-default-runner"
)

# Get Project ID
PROJECT_ID=$(gcloud config get-value project)
echo "Using Project ID: $PROJECT_ID"

echo "Starting deployment of 8 Runners (Internal Ingress, 512MB, 1 vCPU)..."

for entry in "${RUNNERS[@]}"; do
    SERVICE_NAME="${entry%%:*}"
    SOURCE_DIR="${entry##*:}"

    echo "---------------------------------------------------"
    echo "Deploying $SERVICE_NAME (Dockerfile: ./$SOURCE_DIR/Dockerfile) ..."
    
    # 1. Build the image using Cloud Build
    # We use '.' as the build context so that 'COPY shared' works.
    # We use a generic cloudbuild.yaml to specify the Dockerfile path.
    IMAGE_TAG="gcr.io/$PROJECT_ID/$SERVICE_NAME"
    
    echo "Building image: $IMAGE_TAG ..."
    gcloud builds submit . \
        --config=cloudbuild.yaml \
        --substitutions=_DOCKERFILE="$SOURCE_DIR/Dockerfile",_IMAGE="$IMAGE_TAG"
    
    if [ $? -ne 0 ]; then
        echo "❌ Build failed for $SERVICE_NAME"
        exit 1
    fi

    # 2. Deploy the image to Cloud Run
    echo "Deploying image to Cloud Run..."
    URL=$(gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --allow-unauthenticated \
        --ingress internal \
        --memory 512Mi \
        --cpu 1 \
        --concurrency 1 \
        --format 'value(status.url)')
    
    if [ $? -ne 0 ]; then
        echo "Failed to deploy $SERVICE_NAME"
        exit 1
    fi

    echo "Deployed $SERVICE_NAME at $URL"
    RUNNER_URLS[$SERVICE_NAME]=$URL
done

echo "==================================================="
echo "Runners deployed. Deploying API Gateway..."
echo "==================================================="

# Construct Environment Variables for API
# We allow unauthenticated access to the API so the public can use the web UI.
# The API then calls the internal runners via their authenticated (or internal) URLs.
# Note: --allow-unauthenticated on internal services means "allow requests from within the project without IAM token" 
# OR "allow requests from VPC". For Cloud Run-to-Cloud Run (same project), we might need auth or 
# if we set --allow-unauthenticated with --ingress internal, it's open to the project.
# Since the requirement said "Air Gap", internal ingress is key.

ENV_VARS=""
ENV_VARS+="STORAGE_MODE=memory,"
ENV_VARS+="PYTKET_QISKIT_RUNNER_URL=${RUNNER_URLS[pytket-qiskit-runner]},"
ENV_VARS+="PYTKET_CIRQ_RUNNER_URL=${RUNNER_URLS[pytket-cirq-runner]},"
ENV_VARS+="PYTKET_QULACS_RUNNER_URL=${RUNNER_URLS[pytket-qulacs-runner]},"
ENV_VARS+="PYTKET_BRAKET_RUNNER_URL=${RUNNER_URLS[pytket-braket-runner]},"
ENV_VARS+="PYTKET_PROJECTQ_RUNNER_URL=${RUNNER_URLS[pytket-projectq-runner]},"
ENV_VARS+="PYTKET_QUEST_RUNNER_URL=${RUNNER_URLS[pytket-quest-runner]},"
ENV_VARS+="PENNYLANE_LIGHTNING_RUNNER_URL=${RUNNER_URLS[pennylane-lightning-runner]},"
ENV_VARS+="PENNYLANE_DEFAULT_RUNNER_URL=${RUNNER_URLS[pennylane-default-runner]}"

echo "Deploying rosetta-api with runner URLs..."

IMAGE_TAG="gcr.io/$PROJECT_ID/rosetta-api"

echo "Building API image: $IMAGE_TAG ..."
gcloud builds submit . \
    --config=cloudbuild.yaml \
    --substitutions=_DOCKERFILE="rosetta-api/Dockerfile",_IMAGE="$IMAGE_TAG"

if [ $? -ne 0 ]; then
    echo "❌ Build failed for rosetta-api"
    exit 1
fi

API_URL=$(gcloud run deploy "rosetta-api" \
    --image "$IMAGE_TAG" \
    --region "$REGION" \
    --allow-unauthenticated \
    --ingress all \
    --network default \
    --vpc-egress all-traffic \
    --memory 512Mi \
    --cpu 1 \
    --set-env-vars "$ENV_VARS" \
    --format 'value(status.url)')
    
if [ $? -ne 0 ]; then
    echo "Failed to deploy rosetta-api"
    exit 1
fi

echo "==================================================="
echo "Deployment Complete!"
echo "Public API URL: $API_URL"
echo "Runners are secure and internal-only."
echo "==================================================="
