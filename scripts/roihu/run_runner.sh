#!/bin/bash
# Run one job of a runner or compiler SIF the way compose runs its container: same working
# directory and thread pins, payload and result as files. For a Slurm step on Roihu.
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
