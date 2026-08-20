#!/usr/bin/env bash
# Stop hook: refuse to end a session that changed atlas/ without a changelog
# entry. Fires late — writing the entry as you go is cheaper — but it is the
# only thing that catches the omission at all.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0

changed=$(git status --porcelain -- atlas/ 2>/dev/null | wc -l)
[ "$changed" -eq 0 ] && exit 0

if git status --porcelain -- CHANGELOG.md 2>/dev/null | grep -q .; then
  exit 0
fi

echo "atlas/ changed but CHANGELOG.md did not. Add an entry under ## [Unreleased] before wrapping up." >&2
exit 2
