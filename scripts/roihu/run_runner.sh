#!/bin/bash
# Run one job of a runner or compiler SIF the way compose runs its container: same working
# directory and thread pins, payload and result as files. For a Slurm step on Roihu.
# Slurm variables and QROSETTA_IMAGE_SHA256 (the SIF's sha256, computed once per job) are
# passed into the container and recorded in each result as batch_environment.
# Usage: run_runner.sh <image.sif> <run|run_measured|compile> <payload.json> <result.json>
#        run_runner.sh <image.sif> --self-test
set -euo pipefail
SIF=${1:?image.sif}; ENDPOINT=${2:?endpoint or --self-test}
ENV_ARGS=(
  --env OMP_NUM_THREADS=1 --env MKL_NUM_THREADS=1 --env OPENBLAS_NUM_THREADS=1
  --env NUMEXPR_NUM_THREADS=1 --env NUMBA_NUM_THREADS=1
  --env RUNNER_MAX_CONCURRENT=1
  --env MAX_QUBITS_STATEVECTOR="${MAX_QUBITS_STATEVECTOR:-18}"
  --env MAX_QUBITS_MEASURED="${MAX_QUBITS_MEASURED:-24}"
  --env MAX_QUBITS_COMPILE="${MAX_QUBITS_COMPILE:-24}"
)
for var in SLURM_JOB_ID SLURM_STEP_ID SLURM_JOB_PARTITION SLURMD_NODENAME SLURM_CPUS_PER_TASK \
           SLURM_CPU_BIND SLURM_MEM_PER_CPU SLURM_CLUSTER_NAME QROSETTA_IMAGE_SHA256; do
  [ -n "${!var:-}" ] && ENV_ARGS+=(--env "$var=${!var}")
done
BINDS=()
for bind in ${QR_EXTRA_BINDS:-}; do BINDS+=(-B "$bind"); done
APPTAINER=(apptainer exec --containall --cleanenv --pwd /home/appuser/app "${ENV_ARGS[@]}" "${BINDS[@]}")
if [ "$ENDPOINT" = --self-test ]; then
  exec "${APPTAINER[@]}" "$SIF" python main.py --self-test
fi
PAYLOAD=$(realpath "${3:?payload.json}"); RESULT=$(realpath -m "${4:?result.json}")
IO_DIR=$(dirname "$PAYLOAD"); OUT_DIR=$(dirname "$RESULT")
exec "${APPTAINER[@]}" -B "$IO_DIR:/qr-in:ro" -B "$OUT_DIR:/qr-out" "$SIF" \
  python main.py --endpoint "$ENDPOINT" --payload-file "/qr-in/$(basename "$PAYLOAD")" \
  --result-file "/qr-out/$(basename "$RESULT")"
