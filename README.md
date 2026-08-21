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
- **Interventions** — every change you make to how you work gets a before and
  an after, and is kept or discarded on the numbers.
- **Now** — watches the running session and says when it is going backwards.

Ingest, config resolution and handoff exist today. See [docs/status.md](docs/status.md).

## Quick start

```bash
python -m atlas ingest    # read new transcript content
python -m atlas stats     # summarise what has been ingested
python -m atlas config    # what is configured here, and which scope it came from
python -m atlas config --all
python -m atlas handoff   # what docs/status.md claims that the repo contradicts
```

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

Second run of `ingest` reads **0 bytes**. Re-ingest costs new bytes only.

## Testing

```bash
./test.sh
```
