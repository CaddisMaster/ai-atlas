# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-20

**Milestone 1 of 9 is done.** Ingest works against real data.

```
22 transcript files · 52.7 MB · 8,067 messages · 2,590 tool calls
18 main + 4 subagent sessions · 6 days
second run reads 0 bytes
9 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | next |
| 3 | Handoff — reconcile status.md against reality | |
| 4 | Baseline — per-project norms | |
| 5 | Patterns — repeated-sequence detection | |
| 6 | Interventions — before/after measurement | |
| 7 | Now — live session watchdog | |
| 8 | Apply — write config with diff and confirmation | |
| 9 | Demo mode — synthetic transcripts, public landing | |

## Milestone 2 acceptance criteria

Config resolution passes when it correctly reports, for `budget-buddy`:

- 4 subagents — `gotcha-auditor`, `release-prep`, `sweeper`, `test-first`
- 1 slash command — `/wrap`
- 1 `Stop` hook — `changelog-guard.sh`
- 1 skill — `verify`
- a `permissions` block with 27 allow and 3 deny rules

...**and attributes each to the scope it came from.** A naive read of
`~/.claude/settings.json` alone reports none of these, which is exactly the
mistake that produced the first mockup's wrong findings.

## Open questions

- **Transcript retention.** `~/.claude/.last-cleanup` shows a prune runs. The
  actual period has not been established. If it is short, durable ingest matters
  much more than currently claimed.
- **`file-history/`** (6.1 MB) is unread. It is the direct route to detecting
  reverted edits — the strongest signal for the Now screen.
- **What "a session" means** when a transcript is resumed. Not yet examined.
