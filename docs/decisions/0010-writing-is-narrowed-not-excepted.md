# 0010 — Writing is narrowed, not excepted

**Status:** accepted, 2026-08-21. Amends non-negotiable 1.

## Context

Non-negotiable 1 has said since day one: *read-only against `~/.claude`; never
write to it, never move it, never clean it up. It is somebody's irreplaceable
history.*

Milestone 8 writes configuration. Most of it lands in
`<project>/.claude/settings.json`, which is outside `~/.claude` and usually in
the project's own git history. But the user scope — the thing milestone 2 spent
an entire milestone learning to read correctly — is `~/.claude/settings.json`,
inside the directory the rule protects.

Three ways out, and only one of them is honest:

1. **Never write user scope.** Defensible, and it makes the tool useless for the
   scope most likely to hold a permission somebody wants everywhere.
2. **Add an exception**: "read-only except settings.json". An exception to a
   rule of this kind erodes it — the next milestone finds a second file it
   needs, and the rule stops meaning anything.
3. **Narrow the rule to what it was protecting.** The rule exists because
   transcripts, history and file-history are irreplaceable and the tool is not
   their owner. `settings.json` is none of those things: it is configuration,
   the user edits it themselves, and it is small enough to back up completely.

## Decision

**The protected thing is the record, not the directory.** Restated:
transcripts, `history.jsonl`, `file-history/`, plugin state and everything else
under `~/.claude` are read-only, always, with no flag that changes it. Exactly
one file is writable, and only when asked for by name.

The narrowing is enforced in code, not by convention:

- **Project scope is the default.** No flag, and it cannot resolve to anything
  inside `~/.claude`.
- **User scope is opt-in per invocation**, and the guard accepts exactly one
  resolved path: `~/.claude/settings.json`. Any other path under `~/.claude` is
  refused with the same message however it was reached.
- **Paths are resolved before they are checked.** A project `.claude/settings.json`
  that is a symlink into `~/.claude/projects` passes every check made on the
  path as written.
- **Refusing is the default.** Without `--yes`, the diff is printed and nothing
  is written.
- **Backups live beside the database**, never inside `~/.claude`. Restoring must
  not depend on this tool having written into the directory it promises not to
  write into.
- **A malformed settings file is never rewritten.** Reformatting JSON we could
  not parse would silently discard whatever the broken part was.

## Consequences

- `CLAUDE.md` non-negotiable 1 and `SECURITY.md` guarantee 2 are reworded to
  name the record rather than the directory. Neither is weakened in what it
  actually protects.
- Every write is atomic — written to a temporary file and renamed — so an
  interrupted run cannot leave half a settings file behind.
- Applying a change records an intervention with today's date, so a change made
  through this tool is measurable by it afterwards. That is the loop the whole
  project is for.

## What would justify revisiting

A second file under `~/.claude` that genuinely needs writing. The answer is not
to add it to the list: it is to ask whether this tool should be the thing
writing it, and the answer will usually be no. `~/.claude.json` — which holds
the "always allow" answers milestone 2 reads — is the obvious candidate, and it
is deliberately not writable here: it is application state rather than
configuration a person edits.
