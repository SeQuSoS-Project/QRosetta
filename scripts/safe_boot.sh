#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

# --- 0. PRE-FLIGHT CHECK & CONFIGURATION ---
echo ">>> [INIT] Starting safe boot..."

export RUNNER_TIMEOUT_SEC=60


# Define the core services that MUST succeed
CORE_SERVICES=("nginx" "api")

# Define the runner services (can fail without crashing the app)
RUNNERS=(
  "qiskit_runner"
  "cirq_runner"
  "qulacs_runner"
  "braket_runner"
  "projectq_runner"
  "quest_runner"
  "pennylane_runner"
  "pennylane_default_runner"
  "qsim_cirq_runner"
  "pyquil_runner"
  "myqlm_runner"
  "qibo_runner"
  "qrisp_runner"
)

echo ">>> Starting Graceful Build..."

# 1. Build Core Services
echo "[INFO] Building Core Services: ${CORE_SERVICES[*]}"
docker compose build "${CORE_SERVICES[@]}"
if [ $? -ne 0 ]; then
  echo "[CRITICAL] Core services failed to build. Exiting."
  exit 1
fi
echo "[SUCCESS] Core services built successfully."

# 2. Build Runners individually
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

# 3. Start the application
echo ">>> Launching application..."
echo "   Core Services: ${CORE_SERVICES[*]}"
echo "   Active Runners: ${SUCCESSFUL_RUNNERS[*]}"

# Start containers in detached mode first
docker compose up -d "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"

# 4. Stream logs immediately
echo ">>> Attaching to container logs (Press Ctrl+C to stop watching logs)..."
docker compose logs -f