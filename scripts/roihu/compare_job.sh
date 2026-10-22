#!/bin/bash
# One Quantum Rosetta request as one Slurm job: each line of <job_dir>/tasks.tsv is one runner
# or compiler run, executed as its own srun step on one core with run_runner.sh.
# Untested on Roihu (written 2026-10-21 from the CSC documentation; see README.md).
#
# Usage: sbatch --account=<project> --ntasks=<lines in tasks.tsv> compare_job.sh <job_dir> <sif_dir>
# tasks.tsv: <key> TAB <image name without .sif> TAB <run|run_measured|compile>
# Payload of each line: <job_dir>/<key>.payload.json; result: <job_dir>/<key>.result.json
# QR_SEQUENTIAL=1 runs the steps one after another (exclusive timing on a whole node).
#SBATCH --partition=small
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=1G
#SBATCH --time=00:15:00
#SBATCH --hint=nomultithread
set -euo pipefail
JOB_DIR=$(realpath "${1:?job_dir}"); SIF_DIR=$(realpath "${2:?sif_dir}")
HERE=$(cd "$(dirname "$0")" && pwd)
declare -A SHA
while IFS=$'\t' read -r key image endpoint; do
  [ -z "$key" ] && continue
  sif="$SIF_DIR/$image.sif"
  [ -n "${SHA[$image]:-}" ] || SHA[$image]=$(sha256sum "$sif" | cut -d' ' -f1)
  step=(srun --exact --ntasks=1 --cpus-per-task=1 --mem-per-cpu=1G
        --output="$JOB_DIR/$key.log"
        env QROSETTA_IMAGE_SHA256="${SHA[$image]}"
        "$HERE/run_runner.sh" "$sif" "$endpoint" "$JOB_DIR/$key.payload.json" "$JOB_DIR/$key.result.json")
  if [ "${QR_SEQUENTIAL:-0}" = 1 ]; then
    "${step[@]}" || true
  else
    "${step[@]}" &
  fi
done < "$JOB_DIR/tasks.tsv"
wait
