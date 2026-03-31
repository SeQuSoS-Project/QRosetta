#!/bin/bash

echo "========================================================================="
echo "WARNING: You MUST manually replace the <PLACEHOLDER> values (e.g., for DATABASE_URL)"
echo "in this script with your actual credentials before running the deployment."
echo "========================================================================="
echo ""

cd "$(dirname "$0")/.." || exit 1

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
oc create secret generic rosetta-secrets \
    --from-literal=DATABASE_URL="postgresql://qrosetta_admin:IieiHRW2wr%23kE0AzjsNj@86.50.21.2:5432/qrosetta" \
    --from-literal=S3_ACCESS_KEY="9a88f9f05e26435182e63724ec8073f1" \
    --from-literal=S3_SECRET_KEY="297f055f8fc7472a91aa4b1b988afc78" \
    --from-literal=S3_BUCKET_NAME="project_2017360" \
    --dry-run=client -o yaml | oc apply -f -
oc apply -f infra/rahti/runners.yaml
oc apply -f infra/rahti/api.yaml

echo "========================================"
echo "Deployment initiated successfully!"
echo "Run 'oc get pods -n $RAHTI_NAMESPACE' to check the status of your pods."


