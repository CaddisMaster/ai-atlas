# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-21

**Milestones 1, 2 and 3 of 9 are done.** Ingest, config resolution and handoff
all work against real data.

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main + 4 subagent sessions · 4 projects · 7 days
second run reads 0 bytes
every session tied to the project root it ran in
config resolved across 6 scopes, 16 paths checked per project
handoff: 7 checks, clean on this repo, 2 bugs found on the sibling one
39 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | ✅ done |
| 3 | Handoff — reconcile status.md against reality | ✅ done |
| 4 | Baseline — per-project norms | next |
| 5 | Patterns — repeated-sequence detection | |
| 6 | Interventions — before/after measurement | |
| 7 | Now — live session watchdog | |
| 8 | Apply — write config with diff and confirmation | |
| 9 | Demo mode — synthetic transcripts, public landing | |

## Milestone 2 acceptance criteria — met

`python -m atlas config <budget-buddy>` reports, each attributed to `project`:

- 4 subagents — `gotcha-auditor`, `release-prep`, `sweeper`, `test-first` ✅
- 1 slash command — `/wrap` ✅
- 1 `Stop` hook — `changelog-guard.sh` ✅
- 1 skill — `verify` ✅
- 27 allow and 3 deny permission rules ✅

Two things were added beyond the criteria, both because leaving them out would
have reproduced the original mistake in a smaller way:

- `~/.claude.json` `allowedTools` is read as a `dynamic` scope. Those are
  permission grants made by answering a prompt, and they live in no
  `settings.json`. Empty on this machine — fixture-tested only.
- `unknown` is distinguished from `absent` everywhere, and every path checked
  is stored, so "never configured" has evidence behind it. See `decisions/0004`.

## Milestone 3 acceptance criteria — met

`python -m atlas handoff` reports every claim in this file that the repository
contradicts, and reports nothing when the file is current. Both halves matter:
a check that invents findings gets ignored, and an ignored check looks like
evidence.

Seven checks, all deterministic: as-of date against the last commit, roadmap
rows against the changelog's `[Unreleased]` milestones, the newest release tag
against whether this file mentions it, `N tests` against `pytest --collect-only`,
relative links against the filesystem, code committed after the changelog was
last touched, and — only with `--github` — open pull requests.

Pointing it at the sibling project found two defects that this repository could
not have: a crash on `v0.8.0` tags, and a false "stale" from comparing a
PostgreSQL version against a git tag. Both are in `gotchas.md` with regression
tests. That is the second time real data has beaten reasoning, and the argument
for running every new check against a repository that was not written for it.

## Milestone 4 acceptance criteria

Baseline passes when it states, for one project and from ingested data alone,
what a normal session looks like there — length, tool mix, cache behaviour — and
can say which sessions were not normal. It has to survive the obvious objection:
21 main sessions over 7 days is a small sample, so the answer must carry how
confident it is, and `unknown` stays available.

## Open questions

- **Transcript retention.** `~/.claude/.last-cleanup` shows a prune runs. The
  actual period has not been established. If it is short, durable ingest matters
  much more than currently claimed.
- **Plugin scope.** `~/.claude/plugins/` holds one marketplace and no enabled
  plugins, so the code does not read it yet. A plugin supplies commands, agents,
  skills and hooks — every kind config resolution reports — and none of them are
  currently found. This is a known gap, not a solved problem.
- **`--github` is untested and unverifiable offline.** It is the only path in
  the project the test suite cannot exercise. See `decisions/0005`.
- **`file-history/`** (6.1 MB) is unread. It is the direct route to detecting
  reverted edits — the strongest signal for the Now screen.
- **What "a session" means** when a transcript is resumed. Not yet examined.
