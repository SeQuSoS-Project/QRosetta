#!/bin/bash
# Regenerate rosetta-api/static/css/tailwind.css from the classes used in the HTML and JS.
#
# The output is committed, so the pages load one small stylesheet with no build step and
# no network dependency. The previous setup pulled the Tailwind Play CDN at runtime, which
# compiles utilities in the browser on every page load and fails without internet access.
#
# Run this after adding or changing Tailwind classes, then commit css/tailwind.css.
set -eu

cd "$(dirname "$0")/../rosetta-api/static"

if [ ! -x node_modules/.bin/tailwindcss ]; then
    npm install --silent --no-audit --no-fund --no-save tailwindcss@3.4.17
fi

node_modules/.bin/tailwindcss \
    -c tailwind.config.js \
    -i css/tailwind.src.css \
    -o css/tailwind.css \
    --minify

echo "Wrote css/tailwind.css ($(wc -c < css/tailwind.css) bytes)."
echo "Commit it; the pages serve this file directly."
