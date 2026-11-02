#!/usr/bin/env bash
# Validates exported RO-Crate ZIPs against the Process Run Crate 0.5 profile with rocrate-validator
# (installed into $HOME/.tmp/rocrate-venv on first use). Exit status 1 if any crate fails.
# Usage: scripts/verify/validate_crates.sh [-l required|recommended] CRATE.zip ...
set -euo pipefail
level=required
if [ "${1:-}" = "-l" ]; then level=$2; shift 2; fi
[ $# -gt 0 ] || { echo "usage: $0 [-l required|recommended] CRATE.zip ..." >&2; exit 2; }
venv=${ROCRATE_VENV:-$HOME/.tmp/rocrate-venv}
if [ ! -x "$venv/bin/rocrate-validator" ]; then
  python3 -m venv "$venv"
  "$venv/bin/pip" install -q roc-validator==0.13.1
fi
work=$(mktemp -d "${TMPDIR:-$HOME/.tmp}/crate-validate.XXXXXX")
trap 'rm -rf "$work"' EXIT
status=0
for zip in "$@"; do
  dir="$work/$(basename "$zip" .zip)-$RANDOM"
  mkdir -p "$dir"
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$zip" "$dir"
  root=$(dirname "$(find "$dir" -name ro-crate-metadata.json | head -1)")
  if "$venv/bin/rocrate-validator" validate -p process-run-crate-0.5 -l "$level" --no-paging "$root" > "$dir.log" 2>&1; then
    echo "PASS $zip"
  else
    echo "FAIL $zip"; cat "$dir.log"; status=1
  fi
done
exit $status
