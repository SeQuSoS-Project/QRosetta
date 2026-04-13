#!/bin/bash
# Tag, push, apply manifests, and restart pods on Rahti 2.
# Assumes images are already built locally by `docker compose build`.
# Usage: ./scripts/rahti_push.sh [namespace] [service1 service2 ...]
#   namespace  — defaults to "qrosetta"
#   services   — optional subset to push (default: all). E.g.: rosetta-api pennylane-default-runner
# Prerequisite: docker login image-registry.apps.2.rahti.csc.fi

cd "$(dirname "$0")/.." || exit 1

NAMESPACE=${1:-"qrosetta"}
REGISTRY="image-registry.apps.2.rahti.csc.fi/$NAMESPACE"
shift || true   # remaining args are optional service subset

# Maps registry image name -> docker compose service name (used for docker tag)
declare -A SERVICE_MAP=(
    ["rosetta-api"]="api"
    ["pytket-qiskit-runner"]="pytket_qiskit_runner"
    ["pytket-cirq-runner"]="pytket_cirq_runner"
    ["pytket-qulacs-runner"]="pytket_qulacs_runner"
    ["pytket-braket-runner"]="pytket_braket_runner"
    ["pytket-projectq-runner"]="pytket_projectq_runner"
    ["pytket-quest-runner"]="pytket_quest_runner"
    ["pennylane-lightning-runner"]="pennylane_lightning_runner"
    ["pennylane-default-runner"]="pennylane_default_runner"
    ["qsim-cirq-runner"]="qsim_cirq_runner"
    ["pyquil-runner"]="pyquil_runner"
    ["myqlm-runner"]="myqlm_runner"
    ["qibo-runner"]="qibo_runner"
    ["qrisp-runner"]="qrisp_runner"
    ["torch-quantum-runner"]="torch_quantum_runner"
    ["quimb-runner"]="quimb_runner"
    ["cuquantum-runner"]="cuquantum_runner"
)

# Determine which services to push
if [ $# -gt 0 ]; then
    TARGETS=("$@")
else
    TARGETS=("${!SERVICE_MAP[@]}")
fi

echo "========================================"
echo "Registry : $REGISTRY"
echo "Namespace: $NAMESPACE"
echo "Services : ${TARGETS[*]}"
echo "========================================"

set -e

# 1. Tag and push
for NAME in "${TARGETS[@]}"; do
    COMPOSE_SERVICE="${SERVICE_MAP[$NAME]}"
    if [ -z "$COMPOSE_SERVICE" ]; then
        echo "[WARN] Unknown service '$NAME', skipping."
        continue
    fi
    LOCAL_IMAGE="qsimulators-${COMPOSE_SERVICE}"
    REMOTE_TAG="$REGISTRY/$NAME:latest"
    echo ">> Tagging $LOCAL_IMAGE → $REMOTE_TAG"
    docker tag "$LOCAL_IMAGE" "$REMOTE_TAG"
    echo ">> Pushing $REMOTE_TAG"
    docker push "$REMOTE_TAG"
    echo ""
done

# 2. Apply manifests
echo "--- Applying manifests ---"
sed -i "s/<YOUR_NAMESPACE>/$NAMESPACE/g" infra/rahti/rbac.yaml 2>/dev/null || true
oc apply -f infra/rahti/rbac.yaml -n "$NAMESPACE"
oc apply -f infra/rahti/api.yaml  -n "$NAMESPACE"

# 3. Restart the API pod so it picks up the new image
echo "--- Restarting rosetta-api ---"
oc rollout restart deployment/rosetta-api -n "$NAMESPACE"
oc rollout status  deployment/rosetta-api -n "$NAMESPACE" --timeout=120s

echo "========================================"
echo "Done. API is live at:"
oc get route rosetta-api-route -n "$NAMESPACE" -o jsonpath='{"https://"}{.spec.host}{"\n"}'
echo "========================================"
