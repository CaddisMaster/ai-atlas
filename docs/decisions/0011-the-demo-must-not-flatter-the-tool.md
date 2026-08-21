# 0011 — The demo must not flatter the tool

**Status:** accepted, 2026-08-21

## Context

A demo exists to show a stranger what the tool does before they have any data of
their own. The obvious way to build one is to tune the corpus until every screen
looks impressive: a confident baseline, a striking pattern, an intervention with
a clear verdict on every metric.

That would be a lie about this particular tool, and a specific one. Six
milestones were spent making it refuse: no norm below five sessions
(`0006`), no verdict when the split sizes could not produce one (`0008`), no
grade on a single session (`0009`), no permission claim without resolved rules.
On the corpus this project was written against, **most screens refuse most of
the time**. A demo that never refuses teaches the reader the opposite of how the
tool behaves, and the first thing they will do is point it at their own ten
sessions and conclude it is broken.

There is a second temptation: build the demo from a recording of real sessions,
lightly scrubbed. `SECURITY.md` explains why that is not on the table — a real
transcript carries source code, shell output and, eventually, a credential.

## Decision

**The corpus is generated, never recorded.** Every command comes from a small
invented vocabulary; a test asserts that nothing outside it appears.

**The demo contains its own refusals.** Deliberately, not as an accident of
generation:

- a second project with two sessions, which is told it has no normal;
- an intervention dated too late to have an after-half, which cannot be measured;
- metrics inside the same successful comparison that do not clear the corrected
  threshold, shown as "no verdict" next to the ones that do;
- noise sequences that look frequent and are rejected by lift;
- a scope that is unknown rather than absent, on every config screen.

A test asserts that both a `moved` and a `no verdict` appear in the same
measurement. If the generator ever gets tuned until everything moves, that test
fails.

**The effect that is there is real.** The corpus is generated with a genuine
behavioural change halfway through — the four-step ritual is replaced, sessions
get shorter — and the tool is left to find it or not, at ten sessions either
side. It finds it. That is a demonstration rather than a claim, and the screen
says the corpus is synthetic while it does so.

**Every screen says it is synthetic**, in the banner and in the closing line,
including the path to delete.

## Consequences

- The demo is less impressive than it could be, on purpose. It is an accurate
  advertisement rather than a good one.
- The generator carries the same faithfulness burden as the test fixtures:
  abandoned sessions, a subagent carrying its parent's `sessionId`, an
  unmodelled record type, multi-line and compound commands, and a final line
  left half-written.
- Anything found while writing the generator that also affects the detectors
  gets fixed in both. A generator bug and a detector bug look identical from the
  outside — the rotated ritual in `gotchas.md` was three-quarters of an hour of
  suspecting the wrong one.

## What would justify revisiting

Evidence that the demo undersells the tool to the point of being useless — a
reader concluding it does nothing. The answer then is a better *explanation* on
each screen, not better numbers underneath them.
