#!/bin/bash
# Build core services and each runner separately, start whatever built, then follow logs.

cd "$(dirname "$0")/.." || exit 1

echo ">>> [INIT] Starting safe boot..."

# Matches the UI max, config.py default and the Kubernetes manifest.
export RUNNER_TIMEOUT_SEC=300

# Recorded as git_sha in every run report; "-dirty" marks uncommitted changes.
if QROSETTA_GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null); then
  if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    QROSETTA_GIT_SHA="${QROSETTA_GIT_SHA}-dirty"
  fi
else
  QROSETTA_GIT_SHA="unknown"
fi
export QROSETTA_GIT_SHA
echo "[INFO] QROSETTA_GIT_SHA=${QROSETTA_GIT_SHA}"


# A core build failure aborts; a runner build failure only skips that runner.
CORE_SERVICES=("nginx" "api")

RUNNERS=(
  "pytket_qiskit_runner"
  "pytket_cirq_runner"
  "pytket_qulacs_runner"
  "pytket_braket_runner"
  "pytket_projectq_runner"
  "pytket_quest_runner"
  "pennylane_lightning_runner"
  "pennylane_default_runner"
  "qsim_cirq_runner"
  "pyquil_runner"
  "myqlm_runner"
  "qibo_runner"
  "qrisp_runner"
  "torch_quantum_runner"
  "quimb_runner"
  "cuquantum_runner"
)

# Compile-only services; a build failure skips that compiler, as for runners.
COMPILERS=(
  "bqskit_compiler"
  "pyzx_compiler"
  "qmap_compiler"
  "cirq_compiler"
  "staq_compiler"
  "qsynth_compiler"
  "quartz_compiler"
  "synthetiq_compiler"
)

# Builds one compose service with `docker build`, tagged as compose names it. Under podman,
# `docker compose build` goes through the API service, which stages layers in /var/tmp
# whatever TMPDIR or image_copy_tmp_dir says; the CLI honours both.
build_service() {
  local spec
  spec=$(docker compose config --format json 2>/dev/null | python3 -c '
import json, shlex, sys
d = json.load(sys.stdin)
svc = d["services"][sys.argv[1]]
b = svc["build"]
args = " ".join("--build-arg " + shlex.quote(f"{k}={v}") for k, v in (b.get("args") or {}).items())
image = svc.get("image") or d["name"] + "-" + sys.argv[1]
print(shlex.quote(image), shlex.quote(b["dockerfile"]), shlex.quote(b["context"]), args)
' "$1") || return 1
  eval "set -- $spec"
  local image=$1 dockerfile=$2 context=$3
  shift 3
  (cd "$context" && docker build -t "$image" -f "$dockerfile" "$@" .)
}

echo ">>> Starting Graceful Build..."

echo "[INFO] Building Core Services: ${CORE_SERVICES[*]}"
CORE_OK=1
for core in "${CORE_SERVICES[@]}"; do
  build_service "$core" || CORE_OK=0
done
if [ "$CORE_OK" -ne 1 ]; then
  echo "[CRITICAL] Core services failed to build. Exiting."
  exit 1
fi
echo "[SUCCESS] Core services built successfully."

SUCCESSFUL_RUNNERS=()

echo "[BUILD] Building Runners..."
for runner in "${RUNNERS[@]}"; do
  echo "   - Attempting to build $runner..."
  if build_service "$runner"; then
    echo "     [SUCCESS] $runner built."
    SUCCESSFUL_RUNNERS+=("$runner")
  else
    echo "     [!WARNING!] Skipping $runner due to build failure."
  fi
done

echo "[BUILD] Building Compilers..."
for compiler in "${COMPILERS[@]}"; do
  echo "   - Attempting to build $compiler..."
  if build_service "$compiler"; then
    echo "     [SUCCESS] $compiler built."
    SUCCESSFUL_RUNNERS+=("$compiler")
  else
    echo "     [!WARNING!] Skipping $compiler due to build failure."
  fi
done

echo ">>> Launching application..."
echo "   Core Services: ${CORE_SERVICES[*]}"
echo "   Active Runners: ${SUCCESSFUL_RUNNERS[*]}"

docker compose up -d --no-build "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"

echo ">>> Attaching to container logs (Press Ctrl+C to stop watching logs)..."
docker compose logs -f