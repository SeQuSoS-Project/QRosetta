#!/bin/bash
# Build core services and each runner separately, start whatever built, then follow logs.
# QR_BUILD_JOBS builds that many images at a time (default 1); build logs and times go to
# QR_BUILD_LOG_DIR (default ~/.tmp/qrosetta-build); QR_BUILD_ONLY=1 stops after building.
# QR_BUILD_SERVICES builds only the named compose services; QR_ENGINE runs podman instead of docker.
# QR_GIT_SHA is the commit to bake instead of this checkout's (an installed qrosetta building from
# its build kit, which is no git checkout); QR_IMAGE_TAG tags each image <name>:QR_IMAGE_TAG
# instead of <name>:latest; QR_PYTHON is the Python that reads the compose configuration.
# Starting is `qrosetta start`, which puts the stack on standby or removes it on Ctrl-C.

cd "$(dirname "$0")/.." || exit 1

docker() { command "${QR_ENGINE:-docker}" "$@"; }
python3() { command "${QR_PYTHON:-python3}" "$@"; }

# The compose project (image names, labels) is QROSETTA_PROJECT, as for qrosetta.
export QROSETTA_PROJECT="${QROSETTA_PROJECT:-qsimulators}"
export COMPOSE_PROJECT_NAME="$QROSETTA_PROJECT"

echo ">>> [INIT] Starting safe boot..."

# Matches the UI max, config.py default and the Kubernetes manifest.
export RUNNER_TIMEOUT_SEC=300

# Recorded as git_sha in every run report; "-dirty" marks uncommitted changes.
if [ -n "${QR_GIT_SHA:-}" ]; then
  QROSETTA_GIT_SHA="$QR_GIT_SHA"
elif QROSETTA_GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null); then
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

BUILD_CORE=("${CORE_SERVICES[@]}")
BUILD_OTHERS=("${RUNNERS[@]}" "${COMPILERS[@]}")
if [ -n "${QR_BUILD_SERVICES:-}" ]; then
  read -ra REQUESTED <<< "$QR_BUILD_SERVICES"
  BUILD_CORE=()
  BUILD_OTHERS=()
  for svc in "${REQUESTED[@]}"; do
    if [[ " ${CORE_SERVICES[*]} " == *" $svc "* ]]; then BUILD_CORE+=("$svc"); else BUILD_OTHERS+=("$svc"); fi
  done
fi

# Builds one compose service with `docker build`, tagged as compose names it, with the
# org.opencontainers.image.* labels of scripts/release/oci_labels.py. Under podman,
# `docker compose build` goes through the API service, which stages layers in /var/tmp
# whatever TMPDIR or image_copy_tmp_dir says; the CLI honours both.
build_service() {
  local spec oci label
  spec=$(docker compose config --format json 2>/dev/null | python3 -c '
import json, os, shlex, sys
d = json.load(sys.stdin)
svc = d["services"][sys.argv[1]]
b = svc["build"]
args = " ".join("--build-arg " + shlex.quote(f"{k}={v}") for k, v in (b.get("args") or {}).items())
args += "".join(" --label " + shlex.quote(f"{k}={v}") for k, v in (b.get("labels") or {}).items())
image = svc.get("image") or d["name"] + "-" + sys.argv[1]
if os.environ.get("QR_IMAGE_TAG") and ":" not in image.rsplit("/", 1)[-1]:
    image += ":" + os.environ["QR_IMAGE_TAG"]
dockerfile = os.path.join(b["context"], b["dockerfile"])
print(shlex.quote(image), shlex.quote(b["dockerfile"]), shlex.quote(b["context"]), shlex.quote(dockerfile), args)
' "$1") || return 1
  eval "set -- $spec"
  local image=$1 dockerfile=$2 context=$3 dockerfile_path=$4
  shift 4
  oci=$(python3 scripts/release/oci_labels.py "$dockerfile_path" --revision "$QROSETTA_GIT_SHA") || return 1
  while IFS= read -r label; do
    set -- "$@" --label "$label"
  done <<< "$oci"
  set -- "$@" --build-arg "DEBIAN_SNAPSHOT=$(sed -n 's/^DEBIAN_SNAPSHOT=//p' release/debian-snapshot.conf)"
  (cd "$context" && docker build -t "$image" -f "$dockerfile" "$@" .)
}

# Compose services whose runner is registered with enabled=False, read from the API image's
# config.py; they are built only with QR_BUILD_DISABLED=1.
disabled_services() {
  local image hosts
  image=$(docker compose config --format json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d["services"]["api"].get("image") or d["name"] + "-api")') || return 0
  hosts=$(docker run --rm --entrypoint python "$image" -c '
from config import settings
for entry in settings.get_runner_services().values():
    if not entry.get("enabled", True):
        print(entry["base_url"].split("//")[1].split(":")[0])' 2>/dev/null) || return 0
  docker compose config --format json 2>/dev/null | HOSTS="$hosts" python3 -c '
import json, os, sys
hosts = set(os.environ["HOSTS"].split())
for name, svc in json.load(sys.stdin)["services"].items():
    if svc.get("container_name") in hosts:
        print(name)'
}

LOG_DIR="${QR_BUILD_LOG_DIR:-$HOME/.tmp/qrosetta-build}/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
BUILD_JOBS="${QR_BUILD_JOBS:-1}"

# Builds one service into $LOG_DIR/<service>.log and records "<seconds> <ok|failed>".
timed_build() {
  local start=$SECONDS status=ok
  build_service "$1" > "$LOG_DIR/$1.log" 2>&1 || status=failed
  echo "$((SECONDS - start)) $status" > "$LOG_DIR/$1.result"
}

# Builds the given services, at most BUILD_JOBS at a time.
build_all() {
  local svc
  for svc in "$@"; do
    while [ "$(jobs -rp | wc -l)" -ge "$BUILD_JOBS" ]; do wait -n; done
    echo "   - Building $svc (log: $LOG_DIR/$svc.log)"
    timed_build "$svc" &
  done
  wait
}

result_of() { cat "$LOG_DIR/$1.result" 2>/dev/null || echo "0 failed"; }

echo ">>> Starting Graceful Build (${BUILD_JOBS} at a time; logs in $LOG_DIR)..."
BOOT_START=$SECONDS

echo "[INFO] Building Core Services: ${BUILD_CORE[*]}"
build_all "${BUILD_CORE[@]}"
for core in "${BUILD_CORE[@]}"; do
  read -r _ status < <(result_of "$core")
  if [ "$status" != ok ]; then
    tail -20 "$LOG_DIR/$core.log"
    echo "[CRITICAL] Core service $core failed to build. Exiting."
    exit 1
  fi
done
echo "[SUCCESS] Core services built successfully."

SKIPPED=()
if [ "${QR_BUILD_DISABLED:-0}" != 1 ] && [ -z "${QR_BUILD_SERVICES:-}" ]; then
  mapfile -t SKIPPED < <(disabled_services)
fi
TO_BUILD=()
for svc in "${BUILD_OTHERS[@]}"; do
  if [[ " ${SKIPPED[*]} " == *" $svc "* ]]; then
    echo "   - Skipping $svc: its runner is disabled in config.py (QR_BUILD_DISABLED=1 builds it)."
  else
    TO_BUILD+=("$svc")
  fi
done

echo "[BUILD] Building Runners and Compilers..."
build_all "${TO_BUILD[@]}"

SUCCESSFUL_RUNNERS=()
echo "[BUILD] Build times (seconds):"
for svc in "${BUILD_CORE[@]}" "${TO_BUILD[@]}"; do
  read -r seconds status < <(result_of "$svc")
  printf '   %-30s %6s  %s\n' "$svc" "$seconds" "$status"
  if [ "$status" = ok ] && [[ " ${CORE_SERVICES[*]} " != *" $svc "* ]]; then
    SUCCESSFUL_RUNNERS+=("$svc")
  elif [ "$status" != ok ]; then
    echo "     [!WARNING!] Skipping $svc due to build failure (see $LOG_DIR/$svc.log)."
  fi
done
echo "[BUILD] All builds took $((SECONDS - BOOT_START)) s."

if [ "${QR_BUILD_ONLY:-0}" = 1 ]; then
  echo "[INFO] QR_BUILD_ONLY=1: images built, nothing started."
  exit 0
fi

echo ">>> Launching application..."
echo "   Core Services: ${CORE_SERVICES[*]}"
echo "   Active Runners: ${SUCCESSFUL_RUNNERS[*]}"

exec ./qrosetta start "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"
