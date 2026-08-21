# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-21

**Milestones 1 and 2 of 9 are done.** Ingest and config resolution both work
against real data.

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main + 4 subagent sessions · 4 projects · 7 days
second run reads 0 bytes
every session tied to the project root it ran in
config resolved across 6 scopes, 16 paths checked per project
27 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | ✅ done |
| 3 | Handoff — reconcile status.md against reality | next |
| 4 | Baseline — per-project norms | |
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

## Milestone 3 acceptance criteria

Handoff passes when, run against this repository at the start of a session, it
reports every claim in this file that the repository contradicts — a milestone
marked next that the changelog says has landed, a test count that does not match
`pytest`, a date older than the last commit — and reports nothing when the file
is current. It has to find the contradictions without being told which lines to
compare.

The test case is this very file: it has been stale twice already, and the second
time it was stale about milestone 2 while the branch that finished milestone 2
was checked out.

## Open questions

- **Transcript retention.** `~/.claude/.last-cleanup` shows a prune runs. The
  actual period has not been established. If it is short, durable ingest matters
  much more than currently claimed.
- **Plugin scope.** `~/.claude/plugins/` holds one marketplace and no enabled
  plugins, so the code does not read it yet. A plugin supplies commands, agents,
  skills and hooks — every kind config resolution reports — and none of them are
  currently found. This is a known gap, not a solved problem.
- **`file-history/`** (6.1 MB) is unread. It is the direct route to detecting
  reverted edits — the strongest signal for the Now screen.
- **What "a session" means** when a transcript is resumed. Not yet examined.
