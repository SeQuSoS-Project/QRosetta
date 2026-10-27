#!/usr/bin/env bash
# Runs shellcheck over the tracked shell scripts and hadolint over every Dockerfile, failing only on
# findings above the baselines in this directory. Tools come from PATH or $SHELLCHECK / $HADOLINT.
# Usage: scripts/lint/check.sh [shellcheck|hadolint|all] [--write]
set -euo pipefail

cd "$(dirname "$0")/../.."
here=scripts/lint
tool=${1:-all}
extra=()
[ "${2:-}" = --write ] && extra=(--write)
[ "$tool" = --write ] && { tool=all; extra=(--write); }

compare() {
    local name=$1 out=$2
    printf '%s' "$out" | python3 "$here/baseline.py" "$name" "$here/$name.txt" "${extra[@]}"
}

status=0
if [ "$tool" = all ] || [ "$tool" = shellcheck ]; then
    mapfile -t files < <(git ls-files -- 'scripts/*.sh' scripts/hooks/pre-commit scripts/hooks/pre-push)
    rc=0
    out=$("${SHELLCHECK:-shellcheck}" -f json1 "${files[@]}") || rc=$?
    if [ "$rc" -gt 1 ]; then
        echo "shellcheck exited with $rc" >&2
        status=1
    else
        compare shellcheck "$out" || status=1
    fi
fi
if [ "$tool" = all ] || [ "$tool" = hadolint ]; then
    mapfile -t files < <(git ls-files -- '*Dockerfile' '*Dockerfile.*')
    out=$("${HADOLINT:-hadolint}" --no-fail -f json "${files[@]}") || { echo "hadolint failed" >&2; exit 1; }
    compare hadolint "$out" || status=1
fi
exit "$status"
