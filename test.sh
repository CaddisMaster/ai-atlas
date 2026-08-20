#!/usr/bin/env bash
# Lint then test. CI runs the same two commands directly, so this script is a
# convenience rather than a gate of its own.
set -euo pipefail
cd "$(dirname "$0")"

echo "── ruff ──────────────────────────────────────────"
ruff check atlas tests

echo "── pytest ────────────────────────────────────────"
pytest -q "$@"
