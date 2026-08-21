# ai-atlas — working agreement

## What this is

A measurement system for how you work with Claude Code. It reads `~/.claude`,
keeps a durable record, and answers *did that change actually help?*

## Where things are documented

| Question | File |
|---|---|
| What is it, how do I run it | [README.md](README.md) |
| How is it put together | [docs/architecture.md](docs/architecture.md) |
| What is done, what is next | [docs/status.md](docs/status.md) |
| Why is this like this | [docs/decisions/](docs/decisions/) |
| What bit me once already | [docs/gotchas.md](docs/gotchas.md) |
| What we believed that was wrong | [docs/disproven.md](docs/disproven.md) |
| Handling transcript data | [SECURITY.md](SECURITY.md) |
| How versions work | [VERSIONING.md](VERSIONING.md) |

## Non-negotiables

1. **Read-only against `~/.claude`.** Never write to it, never move it, never
   clean it up. It is somebody's irreplaceable history.
2. **Nothing read out of `~/.claude` is transmitted.** Offline by default. The
   one exception is `handoff --github`, opt-in per run, which sends a repository
   name to GitHub and nothing else — see `docs/decisions/0005`. Any new network
   call gets the same treatment or does not land.
3. **Detection is deterministic; drafting may use a model; the final artifact is
   the human's.** A pattern can be *found* by counting. A skill worth having
   contains knowledge that is not in any transcript.
4. **Nothing is dropped silently.** An unrecognised record type is counted, not
   skipped. Format drift must be a number on a page.
5. **Every parsed row carries `PARSER_VERSION`.** Rows either side of a format
   change are not comparable, and the tool must be able to say so.
6. **A measurement whose definition changes is not a measurement.** This is the
   whole premise; changing how something is counted is a versioned event, not a
   tweak.

## Testing

`./test.sh` runs ruff then pytest. Both bugs found so far have regression tests
named after what they broke — keep that habit, it is the only reason they are
findable later.

Fixtures must stay **faithful to real data**, not convenient. The subagent
fixture carries its parent's `sessionId` precisely because real ones do; a
tidier fixture would have hidden the bug.

## Git & development workflow

- Do not work directly on `main`. Branch, PR, squash-merge.
- A `CHANGELOG.md` entry under `## [Unreleased]` goes in the same commit as the
  change. The `Stop` hook catches omissions but fires late.
- Stage deliberately. **Never `git add -A`** — a stray `atlas.db` or scratch
  export would put transcript contents into git history permanently.

## Session wrap-up

Run `/wrap`. It carries the sequence and the traps.

## Current status

Milestones 1–6 work: ingest, config, handoff, baselines, patterns,
interventions. See [docs/status.md](docs/status.md).
