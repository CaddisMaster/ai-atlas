# Disproven

Claims that were believed, acted on, and turned out to be wrong. Kept because
the reasoning that failed is usually more useful than the reasoning that held.

## "You have no hooks, permissions, skills or slash commands" — 2026-08-20

**Believed because** `~/.claude/settings.json` contains three keys: `model`,
`theme`, `autoMode`.

**Wrong because** configuration resolves across enterprise, user, project and
local scopes. `budget-buddy/.claude/` holds four subagents, a `/wrap` command, a
`Stop` hook, a `verify` skill and a full permissions block. Reading one scope
and reporting on all of them produced confident, false findings.

**Consequence:** scope resolution is `decisions/0001` and a milestone of its
own, not an implementation detail.

## "Claude Code transcripts don't disappear, so there is nothing at risk here"
— 2026-08-20

**Believed because** transcripts persist on disk between sessions, unlike the
GeForce NOW logs that rotate every few hours.

**Wrong because** `~/.claude/.last-cleanup` shows a prune process runs on a
schedule. Retention is finite and configurable. The exact period is still
unestablished — see `status.md`.

**Consequence:** durable ingest has a stronger justification than was claimed
when the project was scoped.

## "Analysis by hand is equivalent to a tested ingester" — 2026-08-20

Never stated outright, but assumed while producing statistics with throwaway
scripts. Two of those analyses were wrong: one dropped 4 of 22 files, the other
would have merged subagents into their parents. Both errors were silent and
both were in data being looked at directly.
