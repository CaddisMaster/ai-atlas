# ai-atlas

A measurement system for how you work with Claude Code.

It reads `~/.claude` on your own machine and keeps a durable record of what the
transcripts say. Day to day it answers two questions a chat window cannot:
**what is actually configured here, and where did each piece come from?** and
**what does my status document claim that the repository contradicts?**

Behind those sits the question it was built for — *did that change actually
help?* — which needs more sessions than one person produces in a week. The tool
is candid about that rather than guessing.

> **Nothing leaves this machine.** Transcripts contain source code, credentials
> that passed through shell output, and — if you use Claude Code at work —
> employer data. See [SECURITY.md](SECURITY.md).

## What it does today

Two of these need no sample size at all, and they are the reason to run it:

**Config — what is actually configured here, and where each thing came from.**
Claude Code resolves settings across enterprise, command-line, local, project,
user and `~/.claude.json` scopes. Reading one of them and reporting on all of
them produces confident, false answers — that specific mistake is what started
this project. Every fact comes back with the file it came from, and a scope that
could not be read is `unknown`, never `absent`.

**Handoff — what your status document claims that the repository contradicts.**
A date older than the last commit, a milestone the changelog says has landed, a
test count `pytest` disagrees with, a link to a file that no longer exists. It
found two real defects in a sibling project the first time it was pointed at
one, and it has caught this project's own stale claims twice.

Then two that describe rather than judge:

**Patterns** — tool sequences that repeat across sessions, ranked by how much
more often they happen than chance would predict, with the artifact each one
suggests. **Now** — what the session being written right now is doing, placed
among that project's past sessions, with no score attached.

**Apply** writes an accepted proposal into a settings file, after showing the
diff and refusing by default.

## The long game: did that change actually help?

**Baseline** and **interventions** are the reason the rest exists, and they are
honest about needing more data than one person produces quickly:

```
a norm needs                    5 sessions in a project
a before/after verdict needs    6 sessions either side of the change
```

On the corpus this was written against — four projects, one week — three
projects have no norm and every recorded change is unmeasurable. The tool says
so rather than producing a number:

```
#2  settings.json rewritten (permissions)
    verdict cannot be measured — 2 session(s) before, 7 after, and a side needs 3
```

That is the design working. Six of the nine milestones went into deciding when
*not* to answer: no norm below five sessions, no verdict when the split sizes
could not have produced one whatever the data did, no grade on a single session,
no permission claim without resolved rules. A tool that returns a number anyway
launders noise into evidence about your own working habits.

## How you actually use it

There is no web UI. It is a CLI you run in a project directory.

```bash
python -m atlas ingest                 # costs new bytes only; safe to run often
python -m atlas handoff                # at the START of a session
python -m atlas config                 # when you wonder what is switched on here
python -m atlas patterns               # every week or so
python -m atlas now --watch 5          # in a second pane, while you work
python -m atlas apply . --rule '...'   # when you decide to act on a proposal
```

A realistic loop:

1. **Start of a session:** `handoff`, to find out what the status document is
   lying about before you trust it.
2. **Now and then:** `ingest` — or let it run from a `Stop` hook, since
   correctness never depends on the hook firing.
3. **Weekly:** `patterns` for repeated work worth capturing, `config` before
   claiming you have not configured something.
4. **When you change how you work:** `apply` records it automatically, or
   `intervention add` if you changed it by hand. Then wait. Twelve sessions
   around the change is roughly two weeks of steady work on one project — and
   `intervention list` will keep saying "cannot be measured" until it gets
   there, which is the truthful answer.

## Measured on the machine it was written against

```
25 transcript files · 54.1 MB · 8,455 messages · 2,709 tool calls
21 main sessions + 4 subagent sessions · 4 projects · 7 days
1.47B cache-read tokens · 99.2% cache hit rate
```

`config` resolves one of those projects across six scopes and finds 4 subagents,
1 slash command, 1 skill, 1 `Stop` hook and 30 permission rules — none of which
appear in `~/.claude/settings.json`, which is the only file a naive read looks
at.

`baseline` states a norm for exactly one of the four projects. The other three
have three sessions, two and one, and are told so rather than given a median:

```
budget-buddy   10 counted · 3 excluded (no assistant turn) · provisional
               median session: 120 min · 270 tool calls · 89% of them Bash
               1 session unusual — 49% Bash, 28% Edit, in a project that greps
```

`patterns` finds the work that repeats, ranked by how much more often it happens
than chance — never by how often it happens:

```
4 sessions ·  4× · lift 249   Bash:git add → Bash:git push → Bash:gh pr
                              proposes a slash command
8 sessions · 50× · lift   2   Bash:grep → Bash:sed        ← not reported: chance
```

Every change recorded so far is unmeasurable, and is told so: six sessions
either side is twelve around one change, and no project here has that yet.
Three metrics are pre-registered so that the correction for multiple
comparisons does not eat the evidence — see
[decision 0012](docs/decisions/0012-three-metrics-chosen-in-advance.md).

Second run of `ingest` reads **0 bytes**. Re-ingest costs new bytes only.

## Testing

```bash
./test.sh
```
