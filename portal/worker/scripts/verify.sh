#!/bin/sh
# Typecheck and tests. Silent on success, prints only the failures otherwise.
cd "$(dirname "$0")/.." || exit 1
out=$(npx tsc --noEmit -p . 2>&1 && npx tsc --noEmit -p test 2>&1) || { echo "ERROR: typecheck failed"; echo "$out"; exit 1; }
out=$(npx vitest run 2>&1) || { echo "ERROR: tests failed"; echo "$out" | grep -vE '^ +✓'; exit 1; }
