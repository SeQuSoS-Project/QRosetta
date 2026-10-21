#!/usr/bin/env bash
# Reads file paths on stdin and fails on any that must never be committed: credential files
# and the private working directories that .gitignore excludes (docs/, export/, latex/, CLAUDE.md).
set -euo pipefail

forbidden='(^|/)\.env(\.[^/]*)?$|(^|/)[^/]*openrc[^/]*$|\.(pem|key|p12|pfx|jks|keystore)$|(^|/)id_(rsa|dsa|ecdsa|ed25519)|(^|/)(kubeconfig|clouds\.yaml|\.s3cfg|rclone\.conf|\.netrc|\.pgpass)$|(^|/)\.kube/|(^|/)secrets?/|(^|/)infra/rahti/secret-[^/]*\.yaml$|^docs/|^export/|^latex/|(^|/)CLAUDE\.md$|(^|/)\.claude/|(^|/)memory/|^docker-compose\.override\.yml$'
allowed='(^|/)\.env\.example$|(^|/)infra/rahti/secret-[^/]*\.template\.yaml$'

bad=$(grep -E "$forbidden" | grep -vE "$allowed" || true)
if [ -n "$bad" ]; then
    echo "These files must not be committed (credentials or private notes):" >&2
    printf '%s\n' "$bad" | sed 's/^/  /' >&2
    echo "Unstage them with: git restore --staged <file>" >&2
    exit 1
fi
