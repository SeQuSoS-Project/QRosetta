#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

# Configuration Variables
RAHTI_NAMESPACE=${1:-"my-rahti-project"}
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
)

echo "--- 1. Building and Pushing Images ---"
for SERVICE in "${SERVICES[@]}"; do
    TAG="$REGISTRY/$SERVICE:latest"
    
    if [ "$SERVICE" = "rosetta-api" ]; then
        DOCKERFILE="./rosetta-api/Dockerfile"
    else
        DOCKERFILE="./$SERVICE/Dockerfile"
    fi
    
    echo ">> Building $SERVICE from $DOCKERFILE..."
    docker build -f "$DOCKERFILE" -t "$TAG" .
    
    echo ">> Pushing $TAG..."
    docker push "$TAG"
done

echo ""
echo "--- 2. Manifest Injection ---"
echo "Dynamically injecting namespace '$RAHTI_NAMESPACE' into Kubernetes manifests..."
# Temporarily replace placeholders inside the YAML files
sed -i "s/<your-namespace>/$RAHTI_NAMESPACE/g" infra/rahti/api.yaml
sed -i "s/<your-namespace>/$RAHTI_NAMESPACE/g" infra/rahti/runners.yaml

echo ""
echo "--- 3. Deploying to OpenShift ($RAHTI_NAMESPACE) ---"
oc apply -f infra/rahti/runners.yaml
oc apply -f infra/rahti/api.yaml

echo "========================================"
echo "Deployment initiated successfully!"
echo "Run 'oc get pods -n $RAHTI_NAMESPACE' to check the status of your pods."
