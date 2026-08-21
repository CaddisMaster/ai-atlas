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
