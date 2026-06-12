#!/bin/bash

echo "========================================================================="
echo "WARNING: You MUST manually replace the <PLACEHOLDER> values (e.g., for DATABASE_URL)"
echo "in this script with your actual credentials before running the deployment."
echo "========================================================================="
echo ""

cd "$(dirname "$0")/.." || exit 1

if [ -f .env ]; then
    echo ">> Loading variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo ">> WARNING: .env file not found. Falling back to system environment variables."
fi

# Configuration Variables
RAHTI_NAMESPACE=${1:-"qrosetta"}
REGISTRY="image-registry.apps.2.rahti.csc.fi/$RAHTI_NAMESPACE"

echo "========================================"
echo "Deploying Quantum Rosetta to CSC Rahti"
echo "Namespace: $RAHTI_NAMESPACE"
echo "Registry: $REGISTRY"
echo "========================================"

# Exit immediately if a command exits with a non-zero status
set -e

# Array of services to build and push
SERVICES=(
    "rosetta-api"
    "pytket-qiskit-runner"
    "pytket-cirq-runner"
    "pytket-qulacs-runner"
    "pytket-braket-runner"
    "pytket-projectq-runner"
    "pytket-quest-runner"
    "pennylane-lightning-runner"
    "pennylane-default-runner"
    "qsim-cirq-runner"
    "pyquil-runner"
    "myqlm-runner"
    "qibo-runner"
    "qrisp-runner"
    "torch-quantum-runner"
    "quimb-runner"
    "cuquantum-runner"
)

echo "--- 1. Building and Pushing Images ---"
for SERVICE in "${SERVICES[@]}"; do
    TAG="$REGISTRY/$SERVICE:latest"
    
    if [ "$SERVICE" = "rosetta-api" ]; then
        DOCKERFILE="./rosetta-api/Dockerfile"
    else
        DOCKERFILE="./runners/$SERVICE/Dockerfile"
    fi
    
    echo ">> Building $SERVICE from $DOCKERFILE..."
    docker build -f "$DOCKERFILE" -t "$TAG" .
    
    echo ">> Pushing $TAG..."
    docker push "$TAG"
done

echo ""
echo "--- 2. Manifest Injection ---"
echo "Dynamically injecting namespace '$RAHTI_NAMESPACE' into Kubernetes manifests..."
sed -i "s/<YOUR_NAMESPACE>/$RAHTI_NAMESPACE/g" infra/rahti/rbac.yaml

echo ""
echo "--- 3. Deploying to OpenShift ($RAHTI_NAMESPACE) ---"
oc create secret generic rosetta-secrets \
    --from-literal=DATABASE_URL="${DATABASE_URL}" \
    --from-literal=S3_ACCESS_KEY="${S3_ACCESS_KEY}" \
    --from-literal=S3_SECRET_KEY="${S3_SECRET_KEY}" \
    --from-literal=S3_BUCKET_NAME="${S3_BUCKET_NAME}" \
    --dry-run=client -o yaml | oc apply -f -
oc apply -f infra/rahti/rbac.yaml
oc apply -f infra/rahti/api.yaml
# infra/rahti/runners.yaml is intentionally empty — runners are spawned as K8s Jobs by the API.

echo "========================================"
echo "Deployment initiated successfully!"
echo "Run 'oc get pods -n $RAHTI_NAMESPACE' to check the status of your pods."


