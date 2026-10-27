#!/usr/bin/env bash
# Runs shellcheck over the tracked shell scripts and hadolint over every Dockerfile, failing only on
# findings above the baselines in this directory. Tools come from PATH or $SHELLCHECK / $HADOLINT.
# `semgrep` (not part of `all`: it needs the network for its rule packs) runs Semgrep over the
# Python, JavaScript, nginx and Kubernetes files against semgrep.txt; $SEMGREP names the binary
# (CI installs it from semgrep-requirements.txt).
# Usage: scripts/lint/check.sh [shellcheck|hadolint|semgrep|all] [--write]
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
if [ "$tool" = semgrep ]; then
    out=$("${SEMGREP:-semgrep}" scan --metrics off --disable-version-check --quiet --json \
        --config p/python --config p/javascript --config p/security-audit --config p/secrets \
        --config p/owasp-top-ten --exclude node_modules --exclude rosetta-api/static/vendor \
        --exclude rosetta-api/static/css --exclude tests --exclude latex \
        rosetta-api shared qrosetta_cli runners compilers scripts nginx infra) || {
        echo "semgrep failed" >&2
        exit 1
    }
    compare semgrep "$out" || status=1
fi
exit "$status"
