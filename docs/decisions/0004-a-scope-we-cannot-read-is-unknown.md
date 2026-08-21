# 0004 — A scope we cannot read is unknown, and every place looked is recorded

**Status:** accepted, 2026-08-21

## Context

`0001` established that configuration resolves across all scopes and that every
reported fact carries its scope. Implementing it surfaced a second question that
`0001` only gestured at: what to do about the places we look and find nothing.

Three outcomes are easy to collapse into one and must not be:

- the file **is not there** — absent;
- the file is there and we were **refused** — unknown;
- the file is there and its **JSON does not parse** — unknown.

Collapsing them recreates the original bug. "You have no managed policy" and "we
could not read your managed policy" lead to opposite actions, and the second is
most likely on exactly the machines where policy matters.

Two scopes have no file at all. Flags passed to `claude` are not written
anywhere on disk. And `~/.claude.json` holds `allowedTools` — the "always allow"
answers a user accumulates by pressing a key at a permission prompt — which is a
real permission grant appearing in no `settings.json` in any scope.

## Decision

**`unknown` is a first-class state**, distinct from present and absent, and it
propagates: a scope with any unknown source is unknown overall.

**Every place looked is stored**, found or not, in `config_scopes`. "You have
never configured X" is a claim about where we looked, so the list of places is
the evidence for it and has to survive into the snapshot alongside the findings.

**Command-line flags are reported as an unknown scope** rather than omitted.
A scope that is structurally invisible is worth one line saying so.

**Kinds resolve one of two ways, and which is which is fixed:**

| Kind | Resolution |
|---|---|
| setting, agent, command, skill | highest-precedence scope wins; losers are kept and marked `shadowed` |
| permission rule, hook, mcp server, memory file | additive — every scope's contribution applies |

A shadowed item is kept rather than dropped, because "you have defined this
twice and one of them does nothing" is worth being told.

**Configuration is stored as history, not as current state.** Snapshots are
fingerprinted so an unchanged re-run reuses the existing row. Milestone 6 needs
the configuration as it stood *before* an intervention as much as after it.

## Consequences

- Anything that displays configuration must handle three states. A boolean
  "configured?" is not enough anywhere in the codebase.
- The `dynamic` scope's precedence relative to the file scopes is a guess, and
  is documented as such in `config.PRECEDENCE`. It holds only permission rules,
  which are additive, so the guess changes no answer we currently give.
- Storing settings *values* means the database carries what `SECURITY.md` calls
  the sensitive parts of `settings.json`. Only a short preview plus a hash is
  kept: enough to detect a change, not a second copy of everything.

## What would justify revisiting

The precedence order and the shadowing/additive split are derived from Claude
Code's documented behaviour, not from a resolved-config dump — `0001` already
records that such a dump would replace this subsystem. Short of that, a case
where Claude Code demonstrably resolves a kind differently from the table above
means the table is wrong, and the table is the thing to fix.
