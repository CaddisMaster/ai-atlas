# Current status

> Read at the START of a session. ⚠️ This file lags `main` — reconcile against
> `git log` and the changelog rather than trusting it.
>
> The irony is intentional: automating exactly this reconciliation is the
> project's first real feature.

## Where things are — 2026-08-21

**All nine milestones are done.** The roadmap this project was scoped around is
finished; what is left is in *Open questions* below, and the honest summary is
that the tool now measures more carefully than the available data can support.

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main + 4 subagent sessions · 4 projects · 7 days
second run reads 0 bytes
every session tied to the project root it ran in
config resolved across 6 scopes, 16 paths checked per project
handoff: 7 checks, clean on this repo, 2 bugs found on the sibling one
baseline: a norm for 1 of 4 projects; the other 3 are told they have none
patterns: 198 signatures from 20 tool names; rituals at lift 249, noise at 2
interventions: 4 real changes detected; every one of them unmeasurable, and told so
now: watched this session write itself — 4.5 KB, 0 KB, 6.4 KB across three frames
apply: writes one file kind, refuses everything else, records what it did
demo: 26 synthetic transcripts, one real effect in them, and its own refusals
interventions: 3 pre-registered metrics — a verdict is reachable at 6 a side, not 8
report: one self-contained HTML page that requests nothing when opened
146 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution across all scopes | ✅ done |
| 3 | Handoff — reconcile status.md against reality | ✅ done |
| 4 | Baseline — per-project norms | ✅ done |
| 5 | Patterns — repeated-sequence detection | ✅ done |
| 6 | Interventions — before/after measurement | ✅ done |
| 7 | Now — live session watchdog | ✅ done |
| 8 | Apply — write config with diff and confirmation | ✅ done |
| 9 | Demo mode — synthetic transcripts, public landing | ✅ done |

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

## Milestone 6 acceptance criteria — met

`atlas intervention detect` found four real changes inside the period the
sessions cover, dated from file mtimes. `atlas intervention add` records one
with the date and what the human was hoping for. `atlas intervention list`
measures each against the metrics milestone 4 stores, splitting sessions by the
date, and reports one of four outcomes.

Every real one currently returns a refusal, which is the correct answer:

```
#2  settings.json rewritten (permissions)     2 sessions before,  7 after
#1  rewrote CLAUDE.md                         9 sessions before,  0 after
```

**The finding of this milestone is a number.** Three sessions against three
cannot produce a p-value below 0.2 however cleanly the data separates — four of
the twenty relabellings always tie with the real split. Measured across sizes,
**eight sessions either side** are needed before any verdict is reachable at a
threshold corrected for thirteen metrics. The best-covered project here has ten
sessions in total.

So a comparison can be impossible before the data is looked at, and "no verdict"
would misreport that as *the change did nothing*. There is a fourth outcome —
`cannot separate at this sample size` — and `detect` prints the eight-a-side
figure up front, because it is worth knowing before an experiment. See
`decisions/0008`.

## Milestone 7 acceptance criteria — met

`python -m atlas now` finds the transcript written most recently, catches up on
it — **new bytes only** — and reports what is in it. Run against this repository
while this session was being written, it read 313 KB the first time and 0 the
second, and its "doing" line was the last eight commands actually run.

```
session   78f9221a-…  (main)
so far    147 user turns · 256 assistant turns · 140 tool calls
doing     Bash:git status → Bash:git commit → Bash:gh pr → Bash:ruff check
⚠️  1 past session(s) — too few to place this one against
```

Placed against a project that has a baseline, it states where the session sits
and what it is sitting among — "135 assistant turns, median here 579.5, 22nd of
9 earlier sessions" — and nothing else. **A live session is n = 1**, so there is
no score, no severity and no advice, and `Placement` has no field for one. A
test asserts those fields do not exist, because a field that exists gets printed
eventually. See `decisions/0009`.

**The oldest gap in the test suite is closed.** The partial-line path has been
covered synthetically since milestone 1 and never against a real writer.
`test_ingest_keeps_up_with_a_live_writer` runs a thread appending records in
fragments while the reader catches up in a loop: every record arrives exactly
once and the watermark ends at the end of the file.

## Milestone 8 acceptance criteria — met

`atlas apply` writes a permission rule, a hook entry or a slash-command stub
into a settings file, after printing the exact diff — and **writes nothing
without `--yes`**.

The tension flagged when this milestone was written down is resolved by
narrowing the rule rather than adding an exception to it. The protected thing is
the *record*: transcripts, `history.jsonl`, `file-history/`, plugin state, all
read-only always, with no flag that changes it. Exactly one file under
`~/.claude` is writable, asked for by name — `settings.json`, via
`--scope user`. `CLAUDE.md` non-negotiable 1 and `SECURITY.md` guarantee 2 are
reworded accordingly; neither is weakened in what it protects. See
`decisions/0010`.

End to end on a scratch copy of this project's own settings:

```
diff shown → --yes → rule appended, hooks and prose untouched
backup     → beside the database, never inside ~/.claude
recorded   → intervention #3, dated now, and immediately measurable:
             "cannot be measured — 0 sessions before, 0 after"
```

**A defect found by pointing it at the real user settings file**, before it was
allowed anywhere near a write: `json.dumps` escapes non-ASCII by default, so
adding one three-line rule produced a thirty-line diff that rewrote every em
dash in prose the user had written. A tool that mangles the parts it was not
asked to touch does not get trusted with configuration twice.

## Milestone 9 acceptance criteria — met

`python -m atlas demo` generates a corpus and runs every screen against it. One
command, no Claude Code history required, nothing recorded from anybody.

```
26 transcripts · seeded, so the same seed gives the same corpus
20 sessions in one project, 2 in another, 2 abandoned, 2 subagents
a real behavioural change on day 10 — the ritual replaced by a command
```

What the demo shows, unedited:

```
patterns      10 sessions · 32× · lift 8225   git status → git diff → git add
                                              → git commit → Read:.md
intervention  duration_min  45.1 → 17.8   p=0.001  n=10/10   → moved
              share_Read     0.16 → 0.08  p=0.007  n=10/10     no verdict
              (a second change, dated too late)  cannot be measured
baseline      acme-invoices  established (n=20) · tiny-script  unknown (n=2)
```

The effect is real — it was generated on purpose — and the tool was left to find
it at ten sessions either side. The refusals beside it are the point:
`decisions/0011` records why a demo that never refuses would be a lie about this
particular tool, and a test fails if the generator is ever tuned until
everything moves.

## What is next

The roadmap is finished, so this section replaces it. In rough order of value:

0. **The report page does not explain itself.** Shown the published example, a
   reader who had not built it said, reasonably, that they had no idea what they
   were looking at. It opens with a project name and a wall of numbers, and
   every label on it — `lift 8225`, `cannot separate at this sample size`,
   `provisional` — assumes nine architecture decisions have been read.
   The fix is a plain-English panel at the top saying what the page is, and one
   sentence under each heading saying what its number means in words. This is
   the next thing to do, and it is worth more than any new measurement: a page
   only its author can read is a page that gets shown to nobody.

1. **Reverted-edit detection**, from `file-history/` (6.1 MB, still unread).
   It is the one signal that stands on its own from a single session, so it is
   the only thing that could justify the report or the live screen raising an
   alarm — which is exactly what the original mockup tried to do a milestone too
   early. See `decisions/0009` and `0013`.

2. **Paired comparison.** Whole-session before/after needs six sessions a side
   even after cutting to three pre-registered metrics (`decisions/0012`). Comparing *within* sessions would need far fewer, and needs a
   definition of "the same task" that has to be versioned rather than tuned.
3. **Plugins** are not read by config resolution. They supply commands, agents,
   skills and hooks, so the same class of wrong answer `decisions/0001` exists
   for is still available there.
4. **A release.** Nine milestones and no tag. `VERSIONING.md` says the release
   is the unit, and `0.2.0` is what this state is.

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
- **What "a session" means** when a transcript is resumed. Now measured rather
  than guessed: `gap_max_min` is the largest silence inside a session, and the
  largest in the whole corpus is **23.8 minutes**. So either nothing here was
  resumed after a break, or a resume starts a new transcript. Unresolved, but
  it now has an instrument.
