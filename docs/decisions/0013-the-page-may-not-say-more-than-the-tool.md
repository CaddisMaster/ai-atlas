# 0013 — The page may not say more than the tool

**Status:** accepted, 2026-08-21

## Context

This project began as a mockup: a four-screen dashboard, published as an
artifact on 2026-08-20, which looked convincing enough to build from. Rereading
it after nine milestones, its four headline findings are:

> No permission rules, and 1,996 Bash calls · No hooks configured ·
> Slash commands — Unused · Skills — 0 installed

All four are false, for the reason `decisions/0001` exists: it read
`~/.claude/settings.json` and reported on every scope. Two more of its screens
say things the tool has since proved it must not:

- *"This session is going backwards… sessions with this shape rarely recover."*
  A verdict on one session, which `0009` forbids.
- *"Not holding — violated 6× in 15 sessions."* A before/after verdict at a
  sample size that `0008` and `0012` show cannot support one, with no caveat.

Its own footnote admits the session rows were illustrative. It was an excellent
design and a bad specification, and the gap between them is not visible to
anybody looking at the page.

The HTML report reuses that design. So the risk is specific and immediate: a UI
makes an unsupported claim easier to make and much harder to notice, because it
arrives styled.

## Decision

**Every figure on the page is computed by the library that computes the CLI's
figures.** The renderer calls `resolve`, `build`, `find`, `measure`, `look` and
formats what comes back. It never recomputes anything its own way — that is how
two screens start disagreeing, and the one that looks better wins.

**A refusal is a state, never an error.** Pine is measured, brass is unknown or
untested, grey is absent, and clay — the only alarming colour — is reserved for
a claim the repository contradicts. "Cannot be measured" is the correct answer
to most questions asked here and is styled as ordinary.

**No screen grades a session.** A test asserts the page never contains the words
the mockup used: *going backwards*, *spiral*, *not holding*, *rarely recover*,
*healthy*. A word list is a blunt instrument, and the right one: the temptation
is a UI temptation, and it will return the next time somebody wants the page to
feel more decisive.

**Nothing is requested when the page opens** — no fonts, no scripts, no images.
The page carries project paths and command signatures, and once it is in a
browser none of this project's guarantees follow it.

**Only the synthetic corpus is publishable.** `atlas report` writes to disk.
`atlas demo --html` renders the same page from generated data, and that is the
only version that may become an artifact.

## Consequences

- The report is quieter than the mockup. It has no health chips, no session
  shapes, and no advice — because none of those survived contact with the data.
- Adding a screen means adding the measurement first. The renderer cannot be
  the place a new claim appears.
- The mockup stays published as a record of what was believed before any of it
  was measured. `docs/disproven.md` is the same idea in prose.

## What would revisit this

Reverted-edit detection from `file-history/`. "This file has been edited and
reverted four times in twenty minutes" is a statement about one session that
stands on its own, and it is the only thing that could justify the page raising
an alarm — which is exactly what the mockup's Now screen tried to do a
milestone too early.
