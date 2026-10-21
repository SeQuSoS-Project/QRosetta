#!/bin/bash
# Run rosetta-api/tests/unit inside an API image. The working tree is mounted read-only and copied
# into the container's throwaway layer (tests write ./data); the test requirements are installed
# there too and go away with --rm. Usage: unit_suite.sh <image> [pytest args...]
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
IMAGE=${1:?image}; shift
exec podman run --rm --cpus=2 --memory=4g --user 0:0 \
  -e PYTHONPATH=/work/rosetta-api:/work/shared -e PYTHONDONTWRITEBYTECODE=1 \
  -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$REPO:/repo:ro,z" --entrypoint bash "$IMAGE" -c '
    mkdir /work && tar -C /repo --exclude=./.git --exclude=node_modules -cf - . | tar -C /work -xf -
    cd /work/rosetta-api
    pip install -q --no-cache-dir -r tests/requirements.txt >&2
    python -m pytest -q -n 4 -p no:cacheprovider tests/unit "$@"' bash "$@"
