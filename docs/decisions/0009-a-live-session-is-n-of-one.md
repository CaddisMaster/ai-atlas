# 0009 — A live session is n = 1, so the screen states facts and never grades

**Status:** accepted, 2026-08-21

## Context

Every other measurement in this project compares groups and refuses when the
groups are too small. `decisions/0006` withholds a norm below five sessions;
`decisions/0008` refuses a verdict when the split sizes could not have produced
one. The live screen looks at **one** session, which is the smallest sample
there is.

The pull towards a verdict is strongest here, because a live screen is the one
somebody watches while working. "This session is going badly" is precisely what
a watcher wants to be told — and precisely what one session cannot support. A
session at the 90th percentile for tool calls might be a slog, or the most
productive afternoon of the month. The number does not know which, and neither
does the screen.

There is also a quieter failure mode. A field named `severity`, or a percentile
printed in red, gets read as a judgement whatever the documentation says. The
design has to make the judgement *unavailable*, not merely discouraged.

## Decision

**The screen states facts and places them.** Every number is shown with what it
is being compared against and how many sessions that comparison rests on:
"135 tool calls, median here 270, 22nd of 9 earlier sessions". Below a baseline
of five sessions nothing is placed at all, and the raw counts are still shown.

**No score, no severity, no traffic light, no advice.** `Placement` carries the
metric, the value, the percentile, the median, the band and the count — and
nothing else. A test asserts that no field named `score`, `severity`, `status`,
`verdict` or `healthy` exists on it, because a field that does not exist cannot
be printed by accident later.

`outside_band` is the one flag, and it is derived rather than stored: a value
outside the Tukey band is an arithmetic property of the same numbers already on
screen, not a grade attached to them.

**Nothing about the live view is stored.** Every other subsystem keeps history,
because "did that change help?" needs a before. A live view is the one genuinely
ephemeral thing here: the rows behind it are already in the database, put there
by the same incremental ingest, and a snapshot of how it looked at 14:02 would
be a second copy of a number nobody can act on later.

## Consequences

- The most-asked-for feature — a session health indicator — is one this project
  will not build from one session's numbers. Saying so in an ADR is cheaper
  than relitigating it every time somebody asks.
- The live path reuses milestone 4's metrics and eligibility rules exactly. A
  session measured one way and placed among sessions measured another way is not
  a placement.
- Looking costs new bytes only, which is what makes a two-second refresh
  reasonable at all: the watermark from milestone 1 does the work.

## What would justify revisiting

A within-session signal that does not need a population to interpret — the
reverted-edit detection in `file-history/` is the obvious candidate. "This file
has been edited and reverted four times in twenty minutes" is a statement about
one session that stands on its own, and it is the one thing that could justify
a screen saying something is going wrong.
