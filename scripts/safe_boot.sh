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
)

echo ">>> Starting Graceful Build..."

echo "[INFO] Building Core Services: ${CORE_SERVICES[*]}"
docker compose build "${CORE_SERVICES[@]}"
if [ $? -ne 0 ]; then
  echo "[CRITICAL] Core services failed to build. Exiting."
  exit 1
fi
echo "[SUCCESS] Core services built successfully."

SUCCESSFUL_RUNNERS=()

echo "[BUILD] Building Runners..."
for runner in "${RUNNERS[@]}"; do
  echo "   - Attempting to build $runner..."
  docker compose build "$runner"
  
  if [ $? -eq 0 ]; then
    echo "     [SUCCESS] $runner built."
    SUCCESSFUL_RUNNERS+=("$runner")
  else
    echo "     [!WARNING!] Skipping $runner due to build failure."
  fi
done

echo "[BUILD] Building Compilers..."
for compiler in "${COMPILERS[@]}"; do
  echo "   - Attempting to build $compiler..."
  if docker compose build "$compiler"; then
    echo "     [SUCCESS] $compiler built."
    SUCCESSFUL_RUNNERS+=("$compiler")
  else
    echo "     [!WARNING!] Skipping $compiler due to build failure."
  fi
done

echo ">>> Launching application..."
echo "   Core Services: ${CORE_SERVICES[*]}"
echo "   Active Runners: ${SUCCESSFUL_RUNNERS[*]}"

docker compose up -d "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"

echo ">>> Attaching to container logs (Press Ctrl+C to stop watching logs)..."
docker compose logs -f