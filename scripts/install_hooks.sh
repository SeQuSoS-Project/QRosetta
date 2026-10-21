#!/usr/bin/env bash
# Installs the secret-scanning pre-commit and pre-push hooks and a pinned, checksum-verified gitleaks.
# Run once per clone; the hooks then apply to every branch and worktree of that clone.
set -euo pipefail

GITLEAKS_VERSION=8.30.1

top=$(git rev-parse --show-toplevel)
hooks_dir=$(cd "$(git rev-parse --git-common-dir)" && pwd)/hooks
mkdir -p "$hooks_dir/bin"

os=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$(uname -m)" in
    x86_64|amd64) arch=x64 ;;
    aarch64|arm64) arch=arm64 ;;
    *) echo "unsupported architecture $(uname -m); install gitleaks $GITLEAKS_VERSION on PATH" >&2; exit 1 ;;
esac
platform="${os}_${arch}"
case "$platform" in
    linux_x64) expected=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
    linux_arm64) expected=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
    darwin_x64) expected=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
    darwin_arm64) expected=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
    *) expected= ;;
esac
[ -n "$expected" ] || { echo "no pinned gitleaks build for $platform; install gitleaks $GITLEAKS_VERSION on PATH" >&2; exit 1; }

installed=$("$hooks_dir/bin/gitleaks" version 2>/dev/null || true)
if [ "$installed" != "$GITLEAKS_VERSION" ]; then
    work=$(mktemp -d "${TMPDIR:-$HOME}/gitleaks.XXXXXX")
    trap 'rm -rf "$work"' EXIT
    archive="gitleaks_${GITLEAKS_VERSION}_${platform}.tar.gz"
    curl -fsSL -o "$work/$archive" \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${archive}"
    actual=$( (sha256sum "$work/$archive" 2>/dev/null || shasum -a 256 "$work/$archive") | cut -d' ' -f1)
    [ "$actual" = "$expected" ] || { echo "gitleaks checksum mismatch for $archive" >&2; exit 1; }
    tar -xzf "$work/$archive" -C "$work" gitleaks
    install -m 755 "$work/gitleaks" "$hooks_dir/bin/gitleaks"
fi

install -m 755 "$top/scripts/hooks/pre-commit" "$hooks_dir/pre-commit"
install -m 755 "$top/scripts/hooks/pre-push" "$hooks_dir/pre-push"
install -m 755 "$top/scripts/hooks/forbidden_paths.sh" "$hooks_dir/forbidden_paths.sh"
install -m 644 "$top/.gitleaks.toml" "$hooks_dir/gitleaks.toml"
echo "Installed pre-commit and pre-push secret checks (gitleaks $GITLEAKS_VERSION) in $hooks_dir"
