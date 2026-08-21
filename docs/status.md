# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-21

**Milestones 1–5 of 9 are done.** Ingest, config resolution, handoff, baselines
and patterns all work against real data.

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main + 4 subagent sessions · 4 projects · 7 days
second run reads 0 bytes
every session tied to the project root it ran in
config resolved across 6 scopes, 16 paths checked per project
handoff: 7 checks, clean on this repo, 2 bugs found on the sibling one
baseline: a norm for 1 of 4 projects; the other 3 are told they have none
patterns: 198 signatures from 20 tool names; rituals at lift 249, noise at 2
88 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | ✅ done |
| 3 | Handoff — reconcile status.md against reality | ✅ done |
| 4 | Baseline — per-project norms | ✅ done |
| 5 | Patterns — repeated-sequence detection | ✅ done |
| 6 | Interventions — before/after measurement | next |
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

## Milestone 5 acceptance criteria — met

`python -m atlas patterns` names sequences that repeat across sessions, shows
the session and message each occurrence started at, and proposes the artifact
that fits — and tells a project with one session that it has nothing to say.

```
4 sessions ·  4× · lift 249   Bash:git add → Bash:git push → Bash:gh pr
3 sessions · 21× · lift 370   Edit:.md → Read:.md → Edit:.md
3 sessions ·  3× · lift 151   Bash:docker build → Bash:docker run
276 calls in 9 sessions       Bash:grep — no allow rule in any scope covers it
```

Two things were settled by measuring rather than reasoning, both in
`decisions/0007`:

- **The unit.** 89% of calls are `Bash`, so tool names show nothing. A signature
  — the first two meaningful words of a command, a file's extension, a skill's
  name — gives 198 distinct units from 20 tool names, and never stores a command
  line.
- **The ranking.** The most frequent pair in the corpus, `grep → sed` in 8
  sessions, has a lift of 2.0 — chance. Ranking by frequency buried every real
  ritual. Lift floor 3.0, support floor 3 sessions.

One reported occurrence was checked by hand against the transcript before this
was called done: `200ccdc1`, message `f784bcfa`, `git add -A && git commit …`.

## Milestone 6 acceptance criteria

Interventions passes when a change to how you work — a rule added, a hook
installed, a command written — can be recorded with its date, and the sessions
before and after it compared on the metrics milestone 4 already stores.

The hard part is the same as milestone 4's, one level up: with 10 sessions in
the best-covered project, most before/after comparisons will not be able to
say anything. The honest outcome — "4 sessions before, 6 after, the difference
is well inside the noise" — has to be as easy to reach as a verdict, and the
verdict has to be refused when the numbers cannot carry it.

⚠️ Config snapshots (milestone 2) are fingerprinted and dated, so the *timing*
of a config change is already recorded. An intervention is mostly the join
between that timeline and `session_metrics`, plus the human's note of what they
were trying to achieve.

## Open questions

- **Transcript retention.** `~/.claude/.last-cleanup` shows a prune runs. The
  actual period has not been established. If it is short, durable ingest matters
  much more than currently claimed.
- **Plugin scope.** `~/.claude/plugins/` holds one marketplace and no enabled
  plugins, so the code does not read it yet. A plugin supplies commands, agents,
  skills and hooks — every kind config resolution reports — and none of them are
  currently found. This is a known gap, not a solved problem.
- **Compound commands hide their tail.** `git add -A && git commit` signs as
  `git add`, so a ritual chained into one shell line is invisible to pattern
  detection. Fixing it needs more than one signature per tool call.
- **`--github` is untested and unverifiable offline.** It is the only path in
  the project the test suite cannot exercise. See `decisions/0005`.
- **`file-history/`** (6.1 MB) is unread. It is the direct route to detecting
  reverted edits — the strongest signal for the Now screen.
- **What "a session" means** when a transcript is resumed. Now measured rather
  than guessed: `gap_max_min` is the largest silence inside a session, and the
  largest in the whole corpus is **23.8 minutes**. So either nothing here was
  resumed after a break, or a resume starts a new transcript. Unresolved, but
  it now has an instrument.
