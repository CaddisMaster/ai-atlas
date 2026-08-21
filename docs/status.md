# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-21

**Milestones 1–4 of 9 are done.** Ingest, config resolution, handoff and
baselines all work against real data.

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main + 4 subagent sessions · 4 projects · 7 days
second run reads 0 bytes
every session tied to the project root it ran in
config resolved across 6 scopes, 16 paths checked per project
handoff: 7 checks, clean on this repo, 2 bugs found on the sibling one
baseline: a norm for 1 of 4 projects; the other 3 are told they have none
56 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | ✅ done |
| 3 | Handoff — reconcile status.md against reality | ✅ done |
| 4 | Baseline — per-project norms | ✅ done |
| 5 | Patterns — repeated-sequence detection | next |
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

## Milestone 4 acceptance criteria — met

`python -m atlas baseline` states a norm for `budget-buddy` — 10 sessions
counted, 3 excluded, **provisional** — and refuses for the other three projects,
which have 3, 2 and 1 usable sessions between them. Every definition is frozen
under `BASELINE_VERSION`; see `decisions/0006`.

What it found, on data that was not arranged for it:

```
median session   120 min · 311 user turns · 270 tool calls · 89% Bash
unusual          1 of 10 — 49% Bash, 28% Edit, in a project that otherwise greps
                 2 more on cache hit rate: 0.79 and 0.89 against a 0.96 floor
excluded         3 of 13 — a prompt typed and abandoned, no assistant turn
```

The counting metrics — duration, turns, tool calls — flagged **nothing**, and
the output says why: the middle half of `tool_calls` runs 68 to 343, so the
Tukey fence reaches 755 and would catch almost nothing. That is a true statement
about ten sessions, and it is more useful than a confident-looking threshold.

## Milestone 5 acceptance criteria

Patterns passes when, from ingested data alone, it names a tool sequence that
repeats across sessions, shows the sessions and turns it occurred in so the
claim can be checked by hand, and proposes the artifact that would capture it —
a slash command, a rule, a permission, a subagent, a hook.

It has to be able to find nothing. A project with one session, or with no
repeated sequence above the threshold, gets told that; proposing an artifact on
a single occurrence is how a tool teaches somebody to ignore it.

⚠️ 89% of tool calls in the corpus are `Bash`, so sequence detection over tool
*names* will find `Bash → Bash → Bash` and nothing else. The unit has to carry
more than the tool name — the command's first word or two, the file extension
touched — and choosing that unit is most of this milestone.

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
- **What "a session" means** when a transcript is resumed. Now measured rather
  than guessed: `gap_max_min` is the largest silence inside a session, and the
  largest in the whole corpus is **23.8 minutes**. So either nothing here was
  resumed after a break, or a resume starts a new transcript. Unresolved, but
  it now has an instrument.
