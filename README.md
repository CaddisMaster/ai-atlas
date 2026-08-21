# ai-atlas

A measurement system for how you work with Claude Code.

It reads `~/.claude` on your own machine, keeps a durable record of what
transcripts say before Claude Code prunes them, and answers one question that a
chat window structurally cannot: **did that change actually help?**

> **Nothing leaves this machine.** Transcripts contain source code, credentials
> that passed through shell output, and — if you use Claude Code at work —
> employer data. See [SECURITY.md](SECURITY.md).

## Why this exists rather than just asking Claude

Asking Claude to analyse your transcripts works, and it is the right tool for a
one-off question. It fails at three things:

| | asking in a session | ai-atlas |
|---|---|---|
| Reproducible measurement | a new script, and a new definition, every time | one frozen definition |
| Sees across sessions | only what is in context | the whole corpus |
| Judges a session from outside it | cannot — it *is* the session | separate process |

The third is the important one. A session cannot tell you it is going badly,
and a longitudinal claim — *"this rule has been violated six times since you
added it"* — needs a definition of "violated" that does not change each time
somebody asks.

## What it does

- **Handoff** — checks `docs/status.md` against git, the changelog, the test
  collector and the filesystem, and reports what has gone stale. Open PRs too,
  with `--github`, which is the only thing here that touches the network.
- **Patterns** — finds work you repeat by hand and proposes the artifact that
  captures it: a slash command, a rule, a permission, a subagent, a hook.
- **Baseline** — what a normal session looks like in a project, with the
  sample size attached, and which sessions were not normal.
- **Interventions** — every change you make to how you work gets a before and
  an after, and is kept or discarded on the numbers.
- **Now** — watches the running session and says when it is going backwards.

Everything above the demo mode exists today. See [docs/status.md](docs/status.md).

## Quick start

```bash
python -m atlas ingest    # read new transcript content
python -m atlas stats     # summarise what has been ingested
python -m atlas config    # what is configured here, and which scope it came from
python -m atlas config --all
python -m atlas handoff   # what docs/status.md claims that the repo contradicts
python -m atlas baseline  # what a normal session looks like here, and which were not
python -m atlas patterns  # work that repeats, and the artifact that would capture it
python -m atlas intervention detect   # changes to how you work, found in config and file times
python -m atlas intervention list     # ...and whether the numbers moved
python -m atlas now --watch 5         # what the session being written is doing
python -m atlas apply <project> --rule 'Bash(rg:*)'          # shows the diff, writes nothing
python -m atlas apply <project> --rule 'Bash(rg:*)' --yes    # ...and now writes it
```

`apply` is the only thing here that writes. Project scope is the default and
cannot resolve inside `~/.claude`; the user settings file is opt-in by name and
is the only file under `~/.claude` this tool will ever touch. Backups are kept
outside it. See [SECURITY.md](SECURITY.md).

No dependencies and no install step — ingest is stdlib-only and SQLite ships
with Python. The database lands at `~/.local/share/ai-atlas/atlas.db`; override
with `ATLAS_DB`.

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

And `intervention` answers the question the whole thing is for — usually by
refusing:

```
#2  settings.json rewritten (permissions)
    landed  2026-08-17 12:34 UTC
    verdict cannot be measured — 2 session(s) before, 7 after, and a side needs 3
```

Eight sessions either side are needed before *any* verdict is reachable, at
thirteen metrics. The best-covered project here has ten in total. A tool that
returned a verdict anyway would be laundering noise into evidence about
somebody's own working habits — see [decision 0008](docs/decisions/0008-an-experiment-that-could-not-have-worked.md).

Second run of `ingest` reads **0 bytes**. Re-ingest costs new bytes only.

## Testing

```bash
./test.sh
```
