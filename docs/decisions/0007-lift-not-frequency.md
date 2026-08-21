# 0007 — Lift, not frequency, and a signature instead of a tool name

**Status:** accepted, 2026-08-21

## Context

Two things had to be decided before repeated work could be detected at all, and
both were settled by measuring the corpus rather than by reasoning.

**The unit.** 89% of tool calls in the corpus are `Bash`. A sequence detector
over tool names finds `Bash → Bash → Bash` and stops being a detector. Names had
to carry more.

**The ranking.** With a unit that distinguishes calls, the most frequent
sequences are still worthless:

```
8 sessions · 50×   Bash:grep → Bash:sed     lift 2.0
8 sessions · 26×   Bash:grep → Bash:cat     lift 1.2
4 sessions ·  4×   Bash:git add → Bash:git push → Bash:gh pr    lift 249
```

`grep → sed` is not a habit. Both tools are everywhere, so they land next to
each other by arithmetic — a lift of 1.0 means "exactly as often as chance". The
release ritual happens four times, which frequency ranking buries on page three,
and 249 times more often than its parts predict.

Frequency measures how common the ingredients are. Lift measures whether the
combination means anything.

## Decision

**The unit is a signature**, not a tool name: the first two meaningful words of
a shell command, the extension of a file touched, the name of a skill invoked.
198 distinct signatures where there were 20 tool names. It is deliberately
lossy — `Bash:git commit`, never the commit message — which also means a command
line never reaches the database.

**Ranking and filtering are by lift**, with a floor of 3.0. Support in distinct
sessions remains a separate floor: lift says the combination is real, support
says it is a habit rather than an afternoon.

**Consecutive repeats are collapsed** before mining. How many times in a row you
grepped varies with the file; the shape is what repeats. This also means a run
of one call can never be reported as a sequence — repetition is answered by a
permission rule, not a slash command.

## Consequences

- Every one of these is frozen under `PATTERN_VERSION`, and the signature under
  `PARSER_VERSION` because it is stored on each row at ingest.
- The signature loses compound commands: `git add -A && git commit` signs as
  `git add`, so a ritual chained into one shell line is invisible. Recorded in
  `gotchas.md`; fixing it means more than one signature per call, which the
  one-row-per-call schema does not allow today.
- Lift with small n is noisy by nature — a sequence in 3 of 10 sessions can
  score in the hundreds. Support and the session count are always printed next
  to it so the reader can see how thin the evidence is.

## What would justify revisiting

A corpus where lift stops separating. If most sequences score above the floor,
the floor is doing nothing and the ranking needs a second term — occurrences per
session, or a test against a shuffled baseline. That is measurable: the lift
distribution is one query away, and today it runs 0.6 at the bottom to 370 at
the top with the middle sitting near 2.
