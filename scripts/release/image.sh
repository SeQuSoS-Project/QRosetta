#!/usr/bin/env bash
# Builds or self-tests one release image (.github/workflows/release-images.yml).
#   image.sh build      builds $DOCKERFILE from the repository root as $IMAGE
#   image.sh self-test  runs $SELF_TEST inside $IMAGE without a network
#   image.sh scan       scans $IMAGE with Trivy ($TRIVY_IMAGE, pinned by digest): writes
#                       $SCAN_DIR/trivy.sarif (default trivy/; HIGH and CRITICAL with a fixed
#                       version) and fails on a CRITICAL vulnerability with a fixed version that
#                       .trivyignore does not list
# Environment: ID, DOCKERFILE, LABELS (space-separated key=value), VERSION, IMAGE, SELF_TEST,
# GITHUB_SHA, GITHUB_SERVER_URL, GITHUB_REPOSITORY; NO_CACHE=1 builds without the layer cache and
# pulls the base image; IMAGE_SOURCE (default release) is the identity file's source. The
# org.opencontainers.image.* labels come from scripts/release/oci_labels.py. myQLM, cuQuantum and
# BQSKit are never built here: their licences do not allow the project to distribute their images
# (THIRD_PARTY_NOTICES.md).
set -euo pipefail

TRIVY_IMAGE="ghcr.io/aquasecurity/trivy:0.76.0@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222"

case "${ID:?}" in
  myqlm|cuquantum|bqskit)
    echo "image.sh: $ID is not distributable and is never built by the release pipeline" >&2
    exit 1 ;;
esac
case "${DOCKERFILE:-}" in
  *myqlm-runner/*|*cuquantum-runner/*|*bqskit-compiler/*)
    echo "image.sh: $DOCKERFILE belongs to an image the release pipeline never builds" >&2
    exit 1 ;;
esac

case "${1:-}" in
  build)
    # qrosetta recognises an image as its stack's by these two labels (qrosetta_cli/stack/ownership.py).
    case " ${LABELS:-} " in
      *" org.qrosetta.image.project="[!\ ]*) ;;
      *) echo "image.sh: LABELS lacks org.qrosetta.image.project" >&2; exit 1 ;;
    esac
    case " ${LABELS:-} " in
      *" org.qrosetta.service="[!\ ]*) ;;
      *) echo "image.sh: LABELS lacks org.qrosetta.service" >&2; exit 1 ;;
    esac
    args=()
    for label in ${LABELS:-}; do
      args+=(--label "$label")
    done
    if [ "$ID" = api ]; then
      args+=(--build-arg "QROSETTA_VERSION=${VERSION:?}")
    fi
    case "${IMAGE_SOURCE:=release}" in
      release|built_locally|unknown) ;;
      *) echo "image.sh: IMAGE_SOURCE must be release, built_locally or unknown" >&2; exit 1 ;;
    esac
    if [ "${NO_CACHE:-0}" = 1 ]; then
      args+=(--no-cache --pull)
    fi
    oci=$(python3 scripts/release/oci_labels.py "${DOCKERFILE:?}" --revision "${GITHUB_SHA:?}" \
      --version "${VERSION:?}" --source "${GITHUB_SERVER_URL:?}/${GITHUB_REPOSITORY:?}")
    while IFS= read -r label; do
      args+=(--label "$label")
    done <<< "$oci"
    snapshot=$(sed -n 's/^DEBIAN_SNAPSHOT=//p' "$(dirname "$0")/../../release/debian-snapshot.conf")
    docker build -f "$DOCKERFILE" \
      --build-arg "DEBIAN_SNAPSHOT=${snapshot:?}" \
      --build-arg "QROSETTA_GIT_SHA=$GITHUB_SHA" \
      --build-arg "QROSETTA_IMAGE_SOURCE=$IMAGE_SOURCE" \
      --build-arg "QROSETTA_RELEASE=$VERSION" \
      --label "org.qrosetta.third-party-notices=$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/blob/$GITHUB_SHA/THIRD_PARTY_NOTICES.md" \
      "${args[@]}" -t "${IMAGE:?}" .
    ;;
  self-test)
    docker run --rm --network none \
      -e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 -e OPENBLAS_NUM_THREADS=1 \
      -e NUMEXPR_NUM_THREADS=1 -e NUMBA_NUM_THREADS=1 \
      "${IMAGE:?}" sh -c "${SELF_TEST:?}"
    ;;
  scan)
    out="${SCAN_DIR:-trivy}"
    case "$out" in /*) ;; *) out="$PWD/$out" ;; esac
    cache="${TRIVY_CACHE:-${RUNNER_TEMP:-$HOME/.cache}/trivy}"
    mkdir -p "$out" "$cache"
    trivy() {
      docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$cache:/root/.cache/trivy" \
        -v "$PWD:/src:ro" -v "$out:/out" "$TRIVY_IMAGE" image --scanners vuln --ignore-unfixed \
        --ignorefile /src/.trivyignore --timeout 30m "$@" "${IMAGE:?}"
    }
    trivy --severity HIGH,CRITICAL --format sarif --output /out/trivy.sarif
    trivy --skip-db-update --severity CRITICAL --format table --exit-code 1
    ;;
  *)
    echo "usage: image.sh build|self-test|scan" >&2
    exit 2 ;;
esac
