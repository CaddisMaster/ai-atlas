#!/usr/bin/env bash
# Lint then test. CI runs both commands directly, so this script is a
# convenience rather than a gate of its own.
#
# ⚠️ Prefer .venv/bin over PATH. Unlike the sibling projects this one does not
# run inside a container, so bare `ruff` and `pytest` resolve to whatever the
# shell happens to have — usually nothing. Failing with "command not found"
# after a green-looking session is a bad way to find that out.
set -euo pipefail
cd "$(dirname "$0")"

BIN=".venv/bin"
[ -x "$BIN/ruff" ]   || BIN=""
RUFF="${BIN:+$BIN/}ruff"
PYTEST="${BIN:+$BIN/}pytest"

command -v "$RUFF" >/dev/null 2>&1 || {
  echo "ruff not found. Create the venv first:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt" >&2
  exit 1
}

echo "── ruff ──────────────────────────────────────────"
"$RUFF" check atlas tests

echo "── pytest ────────────────────────────────────────"
"$PYTEST" -q "$@"
