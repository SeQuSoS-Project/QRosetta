#!/bin/bash
# Regenerate rosetta-api/static/css/tailwind.css from the classes used in the HTML and JS.
# Run after changing Tailwind classes, then commit css/tailwind.css.
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
