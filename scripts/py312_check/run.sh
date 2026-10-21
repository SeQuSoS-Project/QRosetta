#!/bin/bash
# Run a py312_check script in an API image against the read-only working tree; outputs go to $OUT.
# Usage: run.sh <image> <script.py> [args...]   (arguments may name /out/<file>)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
IMAGE=${1:?image}; SCRIPT=${2:?script}; shift 2
OUT=${OUT:-$HOME/.tmp/py312_check}
mkdir -p "$OUT"
exec podman run --rm --cpus=2 --memory=4g --user 0:0 \
  -e PYTHONPATH=/repo/rosetta-api:/repo/shared -e PYTHONDONTWRITEBYTECODE=1 \
  -e DATABASE_URL=sqlite:////tmp/x.db \
  -v "$REPO:/repo:ro,z" -v "$OUT:/out:z" -w /repo/rosetta-api \
  --entrypoint python "$IMAGE" "/repo/scripts/py312_check/$SCRIPT" "$@"
