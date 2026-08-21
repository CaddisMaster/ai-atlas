# 0005 — Offline by default; the one network call is opt-in

**Status:** accepted, 2026-08-21

## Context

`SECURITY.md` guarantee 1 says ai-atlas makes no outbound network calls, and
`CLAUDE.md` repeats it as a non-negotiable. Both were written before the handoff
milestone, and the README describes handoff as checking `docs/status.md`
"against git, issues, changelog and open PRs".

Open PRs and issues live on GitHub. There is no local copy. So the feature as
described cannot be delivered under the guarantee as written, and one of the two
had to change.

The guarantee is not really about packets. It is about the data: `~/.claude`
holds source code, credentials that passed through shell output, and employer
data for anyone using Claude Code at work. "Nothing is transmitted" is a promise
about *that*, and asking GitHub which of your own PRs are open transmits none of
it.

## Decision

Everything is offline by default. `handoff` runs its full set of checks — git,
changelog, links, test count, dates, versions — with no network at all.

`--github` is opt-in, per invocation, and shells out to `gh`, using credentials
the user already has. It sends a repository name. It never sends anything read
out of `~/.claude`, and it never sends file contents.

The guarantee is restated rather than dropped: **nothing read out of `~/.claude`
leaves the machine.** That is the promise worth keeping, and it is stronger than
a packet count because it survives contact with features like this one.

## Consequences

- `SECURITY.md` guarantee 1 changes wording, and `CLAUDE.md` non-negotiable 2
  with it. Both now name the data rather than the socket.
- Any future network call gets the same treatment: opt-in, per invocation,
  documented, and carrying nothing from the transcripts. The model layer in
  `SECURITY.md` is already specified this way, so this is the same rule applied
  earlier than expected.
- `--github` is the only code path in the project that cannot be tested offline,
  and it is untested. That is recorded in `docs/testing.md`.

## What would justify revisiting

If `gh` ever needs credentials ai-atlas has to hold itself, this stops being a
thin shell-out and becomes an integration, at which point it needs its own
decision. Reading someone's GitHub token is not something this project should
ever do.
