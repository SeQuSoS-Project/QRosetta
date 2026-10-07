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
IMAGE_TAG=$(git rev-parse --short HEAD)
shift || true

# Registry image name -> docker compose service name.
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
    ["bqskit-compiler"]="bqskit_compiler"
    ["pyzx-compiler"]="pyzx_compiler"
    ["qmap-compiler"]="qmap_compiler"
    ["cirq-compiler"]="cirq_compiler"
    ["staq-compiler"]="staq_compiler"
    ["qsynth-compiler"]="qsynth_compiler"
    ["quartz-compiler"]="quartz_compiler"
    ["synthetiq-compiler"]="synthetiq_compiler"
)

# Left out of a full push: the project's image-stream quota (crq-2017360) is 20.
# Name one explicitly to push it anyway.
SKIP_BY_DEFAULT=(
    pytket-braket-runner
    pytket-projectq-runner
    bqskit-compiler
    cirq-compiler
    qsynth-compiler
)

if [ $# -gt 0 ]; then
    TARGETS=("$@")
else
    TARGETS=()
    for NAME in "${!SERVICE_MAP[@]}"; do
        [[ " ${SKIP_BY_DEFAULT[*]} " == *" $NAME "* ]] || TARGETS+=("$NAME")
    done
fi

echo "========================================"
echo "Registry  : $REGISTRY"
echo "Namespace : $NAMESPACE"
echo "Image Tag : $IMAGE_TAG"
echo "Services  : ${TARGETS[*]}"
echo "========================================"

set -e

for NAME in "${TARGETS[@]}"; do
    COMPOSE_SERVICE="${SERVICE_MAP[$NAME]}"
    if [ -z "$COMPOSE_SERVICE" ]; then
        echo "[WARN] Unknown service '$NAME', skipping."
        continue
    fi
    LOCAL_IMAGE="qsimulators-${COMPOSE_SERVICE}"
    VERSIONED_TAG="$REGISTRY/$NAME:$IMAGE_TAG"
    LATEST_TAG="$REGISTRY/$NAME:latest"
    echo ">> Tagging $LOCAL_IMAGE → $VERSIONED_TAG"
    docker tag "$LOCAL_IMAGE" "$VERSIONED_TAG"
    docker tag "$LOCAL_IMAGE" "$LATEST_TAG"
    echo ">> Pushing $VERSIONED_TAG"
    docker push "$VERSIONED_TAG"
    docker push "$LATEST_TAG"
    echo ""
done

# Runner Jobs are created with IMAGE_TAG, so every image stream not pushed above gets that
# tag on its current :latest.
echo "--- Tagging services not pushed with $IMAGE_TAG ---"
for NAME in "${!SERVICE_MAP[@]}"; do
    [[ " ${TARGETS[*]} " == *" $NAME "* ]] && continue
    if oc get istag "$NAME:latest" -n "$NAMESPACE" >/dev/null 2>&1; then
        oc tag "$NAMESPACE/$NAME:latest" "$NAMESPACE/$NAME:$IMAGE_TAG" -n "$NAMESPACE"
    fi
done

echo "--- Applying manifests ---"
sed -i "s/<YOUR_NAMESPACE>/$NAMESPACE/g" infra/rahti/rbac.yaml 2>/dev/null || true
oc apply -f infra/rahti/rbac.yaml -n "$NAMESPACE"
oc apply -f infra/rahti/api.yaml  -n "$NAMESPACE"

# api.yaml pins rosetta-api:latest, which IfNotPresent will not re-pull, so set the hash
# tag after `oc apply`. The dispatcher uses IMAGE_TAG for runner Job images;
# QROSETTA_GIT_SHA is recorded in experiment manifests.
echo "--- Setting rosetta-api image + IMAGE_TAG=$IMAGE_TAG and restarting ---"
oc set env   deployment/rosetta-api IMAGE_TAG="$IMAGE_TAG" QROSETTA_GIT_SHA="$IMAGE_TAG" -n "$NAMESPACE"
oc set image deployment/rosetta-api api="$REGISTRY/rosetta-api:$IMAGE_TAG" -n "$NAMESPACE"
oc rollout status  deployment/rosetta-api -n "$NAMESPACE" --timeout=120s

echo "========================================"
echo "Done. API is live at:"
oc get route rosetta-api-route -n "$NAMESPACE" -o jsonpath='{"https://"}{.spec.host}{"\n"}'
echo "========================================"
