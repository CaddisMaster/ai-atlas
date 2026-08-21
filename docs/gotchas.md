# Gotchas

Things that cost time once. Each is load-bearing somewhere in the code.

## Subagent transcripts sit one level deeper

```
projects/<project>/<session>.jsonl                        main
projects/<project>/<session>/subagents/agent-<id>.jsonl    subagent
```

A glob of `*/*.jsonl` finds main sessions only. It dropped 4 of 22 files —
1.0 MB, every subagent run — in the analysis that motivated this project.
Use `rglob`. Guarded by a test.

## A subagent's `sessionId` is its parent's

All four subagent transcripts on the machine this was written against carry the
parent session's id, not their own. Keying session identity on that field merges
the subagent into its parent and — depending on which file is read first —
relabels the parent as a subagent.

**Identity comes from the file path.** `path.stem` for subagents, the record's
`sessionId` for main sessions.

## The watermark's prefix hash must cover consumed bytes only

Hashing a fixed 4 KB window means any transcript smaller than 4 KB changes its
own hash every time a line is appended, invalidating its watermark and forcing a
full re-read — for exactly the small, actively-growing files where incremental
ingest matters most. Cap the hash length at `min(PREFIX_BYTES, last_offset)`.

## An active transcript ends mid-line

A session being written right now has an incomplete final line. Consuming it
loses the record when the rest arrives. Stop at the last complete line and leave
the watermark before the partial one.

## Unmodelled record types appear without warning

Present on day one and not in any documentation: `pr-link` (438),
`atis-latch` (225), `frame-link` (20), `artifact-comment-monitor` (3). They are
counted in `record_types` with `known = 0`. Check that table after any Claude
Code update — it is the drift alarm.

## `test.sh` must prefer `.venv/bin` over `PATH`

Unlike the sibling projects, this one does not run inside a container, so bare
`ruff` and `pytest` resolve to whatever the shell happens to have — usually
nothing. The script checks `.venv/bin` first and fails with the venv-creation
command rather than a bare "command not found".

## A `projects/` directory name cannot be decoded back into a path

`/home/sean/dev/ai-atlas` becomes `-home-sean-dev-ai-atlas`, and both `/` and a
literal `-` end up as `-`. So `-home-sean-personal-projects` is either
`/home/sean/personal-projects` or `/home/sean/personal/projects` and the name
does not say which — and this machine has *both* a `personal-projects` directory
and projects inside it.

Encoding is a function; decoding is not. The project root comes from the `cwd`
field on the transcript's own records, confirmed by encoding it back and
matching. A candidate that fails to match yields `None` — "unknown" — never a
plausible wrong path.

`cwd` is per record and a session wanders: one real transcript records 1,331
records at the project root and 18 from `app/templates/partials`. Walk up from
`cwd` until an ancestor matches.

## Permission rules live outside `settings.json` too

`~/.claude.json` carries `projects.<root>.allowedTools`: the "always allow"
answers accumulated by pressing a key at a permission prompt. They grant
permissions exactly like a rule in `settings.json` and appear in no settings
file in any scope. An audit that reads only settings files reports fewer
permissions than are in force.

They are all empty on this machine, which is the worst case for a bug: the code
path is exercised by fixtures only. See `tests/conftest.py`.

## A skill is named for its directory, not its file

Every skill file is called `SKILL.md`, so `path.stem` names all of them "SKILL".
The name is the parent directory's.

## `\b` does not match between `v` and `0`

`v0.8.0` contains no word boundary before the digit, so `\b(\d+)\.` finds
nothing in it and every release tag on the sibling project parsed as *no version
at all* — then `max()` raised on the empty list. This repository has no tags, so
the check passed its own tests and crashed on the first real repository it saw.

Use `(?<![\w.])v?(\d+)\.(\d+)\.(\d+)(?![\w.])`. Guarded by
`test_a_v_prefixed_tag_is_still_a_version`.

## A per-file test count is not a repository total

`` `tests/test_design_system.py` (10 tests) `` is a claim about one file. Compared
against what pytest collects for the whole repository, it reads as a
contradiction that is not there — and a staleness check that invents findings
gets switched off, which is worse than not having one. Lines naming a file are
skipped.

The same applies to versions: a status document mentions the versions of what it
depends on, and the first run of the version check compared PostgreSQL 10.15.0
against a git tag. The only comparable version is one that exists as a tag on
the repository being checked.

## Three of thirteen sessions have no assistant turn

A prompt typed and abandoned, or a session that never got a reply. They are
real rows with real timestamps and a duration of 0.0 minutes, and they drag
every median toward zero if counted. `budget-buddy` has three of them out of
thirteen; `material-list-import-tool` has two out of four.

A session counts toward a baseline only if it has at least one assistant turn —
and the ones left out are stored in `baseline_exclusions` with the reason,
because a number that quietly ignores a quarter of the corpus is worse than no
number.

## `sessions.started` and `ended` do not exist until they are derived

There is no "session ended" record in a transcript, so ingest computes both
columns with an `UPDATE` after reading. Anything that inserts session rows
directly — a test fixture, say — has rows with `NULL` boundaries and every
duration metric silently disappears, because a missing value is absent from
that metric by design. The fixture in `tests/conftest.py` runs the same
`UPDATE` for that reason.

## Pooled tool counts let the longest session define "normal"

Counting a project's tool calls in aggregate answers "what does this project
use", not "what does a session here look like". One 2,000-call session out of
six sets the mix on its own.

Shares are computed per session and then summarised. On the corpus this was
written against, the two answers disagree in a way that matters: sessions are
89% Bash at the median, and the one session that was 49% Bash and 28% Edit is
the only one the baseline calls unusual.

## A changelog's prose mentions milestones that have not landed

`### Added — milestone 4, baselines` is a claim that milestone 4 shipped.
"…which is what milestone 6 will compare before and after" is a plan, in a
sentence inside that same section. Scanning the whole `[Unreleased]` body for
`milestone N` cannot tell them apart, and reported an empty roadmap row as
stale.

Headings only. Found by handoff, in this repository, one commit after the
sentence was written — which is the best evidence so far that the milestone
was worth building.

## A third of shell commands are multi-line

`cd /home/sean/project\nsed -n '60,120p' test.sh` is one `Bash` call with a
newline in it. Splitting commands on `&&`, `;` and `|` but not `\n` left the
`cd` in front of everything, and 48 calls landed in a bucket named `?`.

Newlines separate commands as surely as `&&` does. Guarded by
`test_a_command_reduces_to_its_first_two_meaningful_words`.

## A compound command hides everything after the first program

`git add -A && git commit -q -F -` signs as `Bash:git add`. The commit is
invisible, so a ritual somebody chained into one shell line is invisible too —
sequence detection only sees rituals spread across separate calls.

Not fixed: it needs more than one signature per tool call, and the schema is one
row per call. Worth knowing before concluding that somebody has no habits.

## One assistant message can make several tool calls

So a message uuid does not identify an occurrence of anything. Keying
`pattern_occurrences` on `(run, sequence, session, message_uuid)` collides the
moment two calls in one message start the same sequence — which a test fixture
hit immediately, because a fixture puts every call in one message.

The position in the session's sequence is the identifier. The message uuid stays
alongside it, because that is what makes a finding checkable by hand.

## The most frequent sequence is the least meaningful one

`grep → sed`, in 8 sessions, 50 times, is not a habit — both tools are
everywhere and land next to each other by arithmetic. Its lift is 2.0.
`git add → git push → gh pr` happens 4 times and scores 249.

Rank by lift, filter by lift, and keep support in sessions as a separate floor.
See `decisions/0007`.

## Three sessions against three cannot beat p = 0.2

Twenty relabellings, four of which always tie with the real split. Perfectly
separated data — 500 minutes against 1 minute — still scores 0.2. Eight either
side is the first symmetric split that clears a threshold corrected for thirteen
metrics.

So a comparison can be impossible before the data is looked at, and saying "no
verdict" there reads as *the change did nothing*. Compute the floor the sizes
admit, and say `cannot separate at this sample size` instead. See
`decisions/0008`.

## A file mtime is the only date available for anything done before this tool

Config snapshots only start when `atlas config` first runs, so every change made
before that is invisible to snapshot diffing. `.claude/settings.json` and
`CLAUDE.md` carry mtimes, which are exact about *when* and silent about *what*
— and only report the **last** write, not each earlier one.

Both detection paths are kept and labelled, because a sharp date with a vague
description is still the difference between measurable and not.

## A session in flight belongs to neither side

A session that started before a change landed and ended after it saw both
worlds. Counting it either way misstates which world it was in. It is excluded
and reported — one of the thirteen real sessions is in exactly this position for
two of the four detected changes.
