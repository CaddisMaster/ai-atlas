---
description: End-of-session wrap-up — test, changelog, status, PR, merge.
---

Run the session wrap-up for this repo.

`CLAUDE.md` is the source of truth for *policy*. This command carries the
**sequence** and the **traps**. If the two disagree, `CLAUDE.md` wins and this
file is what needs fixing.

Work through the steps in order, reporting after each. Stop and ask rather than
skipping — the ordering is the point.

## 1. Tests, in full

`./test.sh` — ruff then pytest. Confirm it has actually been run **this
session**, not that it passed earlier.

If a bug was fixed, there must be a regression test named after what broke, with
a comment saying how it was found. Both existing ones came from running against
real data rather than from reasoning; that ratio is expected, not embarrassing.

## 2. Changelog and status

- An entry under `## [Unreleased]` in `CHANGELOG.md`, written for someone
  reading it in a year: what changed and why it matters, not what the diff says.
- If a milestone moved, update the table in `docs/status.md`.
- If something turned out to be wrong, add it to `docs/disproven.md`. That file
  is the point of the project in miniature — do not skip it because the entry is
  unflattering.
- If a decision was locked, add a record in `docs/decisions/` with its reversal
  condition.

## 3. Stage deliberately

⚠️ **Never `git add -A`.** This repo sits next to a database built from
transcripts containing source code, credentials and employer data. Name the
paths being staged and show `git status --short` before committing.

`*.db` is gitignored, but a gitignore is a convenience, not a guarantee.

## 4. PR and merge

Do not work directly on `main`. Open the PR with `Closes #<issue>` where one
applies, wait for green, squash-merge.
