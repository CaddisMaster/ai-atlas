# 0001 — Config resolves across all scopes

**Status:** accepted, 2026-08-20

## Context

Claude Code resolves configuration across enterprise, user, project and local
scopes. A user-level `settings.json` is one input among several, not the
configuration.

While scoping this project, an analysis read `~/.claude/settings.json` alone —
three keys — and reported that the user had no hooks, no permission rules, no
skills and no slash commands. All four claims were false. `budget-buddy/.claude/`
holds four subagents, `/wrap`, a `Stop` hook, a `verify` skill and a permissions
block with 30 rules.

The product's central claim is *"here is what you are not using."* A tool that
gets that wrong is worse than no tool, because it is confidently wrong and its
recommendations are actionable.

## Decision

Scope resolution is a first-class subsystem with its own milestone, not an
implementation detail of a settings reader.

Every reported configuration fact carries **the scope it came from**. The UI
never shows a setting without showing where it was resolved from.

Where a scope cannot be read — an enterprise policy the user has no access to —
the answer is "unknown", never "absent".

## Consequences

- Milestone 2 exists, and its acceptance criteria are the specific things the
  naive read missed (see `docs/status.md`).
- "Never configured" is a claim requiring evidence from every scope, so it is
  expensive. That is correct: it is also the claim most likely to be acted on.
- `unknown` is a third state throughout, alongside present and absent.

## What would justify revisiting

If Claude Code ever exposes a resolved-configuration command — a single
authoritative dump of effective config with provenance — this subsystem should
be deleted and replaced by a call to it. Deriving what a tool can report about
itself is a workaround, not a goal.
