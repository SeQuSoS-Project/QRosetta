#!/usr/bin/env bash
# Requalify a runner or compiler image on a new Python base (old vs new image: fixed-seed corpus,
# self-test, timing on one CPU, optional Trivy scan). Usage and options: requalify.sh --help.
#   scripts/requalify/requalify.sh qulacs python:3.12-slim@sha256:...       prepare + requalify
#   scripts/requalify/requalify.sh qulacs --candidate DIR                    requalify a candidate
# Temporary files go to $TMPDIR (default $HOME/.tmp); never /tmp.
set -euo pipefail
export TMPDIR="${TMPDIR:-$HOME/.tmp}"
case "$TMPDIR" in /tmp*|/var/tmp*) export TMPDIR="$HOME/.tmp" ;; esac
mkdir -p "$TMPDIR"
exec "${PYTHON:-python3}" "$(dirname "$0")/requalify.py" "$@"
