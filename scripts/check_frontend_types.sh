#!/bin/bash
# Type-check the frontend with `tsc --checkJs` (emits nothing).
# Any diagnostic other than TS2339 fails. TS2339 (mostly untyped getElementById results)
# fails only if its count exceeds TS2339_BASELINE; lower the baseline as it shrinks.
set -u

TS2339_BASELINE=60

cd "$(dirname "$0")/../rosetta-api/static" || exit 1

if [ ! -x node_modules/.bin/tsc ]; then
    npm install --silent --no-audit --no-fund --no-save typescript@5.6.3 || exit 1
fi

OUT=$(node_modules/.bin/tsc -p tsconfig.json 2>&1)

HARD=$(printf '%s\n' "$OUT" | grep -E 'error TS' | grep -v 'TS2339' || true)
DOM_COUNT=$(printf '%s\n' "$OUT" | grep -cE 'error TS2339' || true)

STATUS=0

if [ -n "$HARD" ]; then
    echo "Frontend type errors:"
    printf '%s\n' "$HARD"
    STATUS=1
fi

if [ "$DOM_COUNT" -gt "$TS2339_BASELINE" ]; then
    echo "Untyped DOM access grew: $DOM_COUNT (baseline $TS2339_BASELINE)."
    echo "Give the new element a concrete type, e.g."
    echo "  /** @type {HTMLInputElement} */ (document.getElementById('x'))"
    printf '%s\n' "$OUT" | grep -E 'error TS2339'
    STATUS=1
elif [ "$DOM_COUNT" -lt "$TS2339_BASELINE" ]; then
    echo "Untyped DOM access is down to $DOM_COUNT (baseline $TS2339_BASELINE)."
    echo "Lower TS2339_BASELINE in $0 to lock the improvement in."
fi

[ "$STATUS" -eq 0 ] && echo "Frontend types OK (untyped DOM access: $DOM_COUNT/$TS2339_BASELINE)."
exit "$STATUS"
