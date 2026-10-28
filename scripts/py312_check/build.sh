#!/bin/bash
# Build $DOCKERFILE (default rosetta-api/Dockerfile) as $PY312_IMAGE (default localhost/py312-api:test)
# with the requal label (2 CPUs, 4g, layers under ~/.tmp).
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$HOME/.tmp/podman-build"
cd "$REPO"
TMPDIR="$HOME/.tmp/podman-build" podman build --memory 4g --cpu-period 100000 --cpu-quota 200000 \
  --label org.qrosetta.image.project=requal \
  --build-arg QROSETTA_GIT_SHA="$(git -C "$REPO" rev-parse --short HEAD)" \
  -t "${PY312_IMAGE:-localhost/py312-api:test}" -f "${DOCKERFILE:-rosetta-api/Dockerfile}" .
