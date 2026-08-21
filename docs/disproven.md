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
own, not an implementation detail. Landed 2026-08-21 and guarded by
`test_project_scope_is_not_missed_by_a_user_scope_read`, which fails if a
resolution ever reports on scopes it did not read.

**Still true in a smaller way:** plugins supply commands, agents, skills and
hooks, and nothing reads `~/.claude/plugins/` yet. The same class of wrong
answer is available there — see `status.md`.

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

## "The mockup is a specification" — 2026-08-20

**Believed because** it was detailed, it looked right, and its four findings
were specific enough to act on.

**Wrong because** every one of those findings was produced by reading one scope
— `docs/decisions/0001` — and two of its screens made claims the sample sizes
could not support: a verdict on a single session, and rule verdicts at nine to
fifteen sessions with no caveat. Its own footnote admitted the session rows were
illustrative.

**Consequence:** the HTML report reuses the mockup's *design* and none of its
claims, and `decisions/0013` fixes what a rendered page is allowed to say. The
mockup stays published: it is the clearest record of what this project believed
before it measured anything.
