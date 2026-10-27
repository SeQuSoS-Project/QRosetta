#!/usr/bin/env bash
# Builds or self-tests one release image (.github/workflows/release-images.yml).
#   image.sh build      builds $DOCKERFILE from the repository root as $IMAGE
#   image.sh self-test  runs $SELF_TEST inside $IMAGE without a network
# Environment: ID, DOCKERFILE, LABELS (space-separated key=value), VERSION, IMAGE, SELF_TEST,
# GITHUB_SHA, GITHUB_SERVER_URL, GITHUB_REPOSITORY. myQLM, cuQuantum and BQSKit are never built here:
# their licences do not allow the project to distribute their images (THIRD_PARTY_NOTICES.md).
set -euo pipefail

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
    docker build -f "${DOCKERFILE:?}" \
      --build-arg "QROSETTA_GIT_SHA=${GITHUB_SHA:?}" \
      --build-arg "QROSETTA_IMAGE_SOURCE=release" \
      --build-arg "QROSETTA_RELEASE=${VERSION:?}" \
      --label "org.opencontainers.image.version=$VERSION" \
      --label "org.opencontainers.image.revision=$GITHUB_SHA" \
      --label "org.opencontainers.image.source=${GITHUB_SERVER_URL:?}/${GITHUB_REPOSITORY:?}" \
      --label "org.qrosetta.third-party-notices=$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/blob/$GITHUB_SHA/THIRD_PARTY_NOTICES.md" \
      "${args[@]}" -t "${IMAGE:?}" .
    ;;
  self-test)
    docker run --rm --network none \
      -e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 -e OPENBLAS_NUM_THREADS=1 \
      -e NUMEXPR_NUM_THREADS=1 -e NUMBA_NUM_THREADS=1 \
      "${IMAGE:?}" sh -c "${SELF_TEST:?}"
    ;;
  *)
    echo "usage: image.sh build|self-test" >&2
    exit 2 ;;
esac
