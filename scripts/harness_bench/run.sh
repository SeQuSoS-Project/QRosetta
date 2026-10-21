#!/bin/bash
# Run a harness_bench script inside the API image against the working tree, with the
# reference analysis package taken from a git ref. Usage: run.sh <ref> <script.py> [args...]
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
REF=${1:?git ref}; SCRIPT=${2:?script}; shift 2
IMAGE=${QR_BENCH_IMAGE:-localhost/qsimulators-api:latest}
WORK=${QR_BENCH_WORK:-$HOME/.tmp/harness_bench}
REF_DIR="$WORK/ref-$(git -C "$REPO" rev-parse --short "$REF")"
if [ ! -d "$REF_DIR/divergence" ]; then
  mkdir -p "$REF_DIR"
  git -C "$REPO" archive "$REF" rosetta-api/services/analysis/divergence | tar -x -C "$REF_DIR"
  mv "$REF_DIR/rosetta-api/services/analysis/divergence" "$REF_DIR/divergence"
  rm -rf "$REF_DIR/rosetta-api"
fi
exec podman run --rm --cpus="${QR_BENCH_CPUS:-1}" --memory="${QR_BENCH_MEMORY:-4g}" \
  -e PYTHONPATH=/repo/rosetta-api:/repo/shared -e PYTHONDONTWRITEBYTECODE=1 \
  -e QROSETTA_GIT_SHA="$(git -C "$REPO" rev-parse --short HEAD)" \
  -v "$REPO:/repo:ro,z" -v "$REF_DIR:/ref:ro,z" -w /repo/rosetta-api \
  --entrypoint python "$IMAGE" "/repo/scripts/harness_bench/$SCRIPT" /ref/divergence "$@"
