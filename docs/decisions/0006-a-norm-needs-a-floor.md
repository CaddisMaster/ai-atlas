# 0006 — A norm needs a floor, and below it the answer is "unknown"

**Status:** accepted, 2026-08-21

## Context

The point of a baseline is to support a sentence like *"that session used four
times the tool calls of a normal one here"*. That sentence is worth having only
if "normal" means something. On the corpus this was written against:

```
budget-buddy            13 main sessions, 3 of them with no assistant turn
material-list-import    4, two of them abandoned
personal-projects       3
ai-atlas                1
```

One project has ten usable sessions. The others have three, two and one. A
median of two sessions is arithmetic, not a norm, and a tool that prints it
without comment is inviting somebody to act on noise — while looking precise,
which is worse than looking uncertain.

The temptation is to print the number anyway, because a tool that says "I don't
know" feels broken. It is not broken. Three of four projects here genuinely do
not have enough history to have a normal yet, and that is a true and useful
thing to be told.

## Decision

**Confidence comes from n alone**, and it gates what is claimed:

| n | confidence | what is stated |
|---|---|---|
| < 5 | `unknown` | the values, and no band or outliers at all |
| 5–11 | `provisional` | everything, labelled as indicative |
| ≥ 12 | `established` | everything |

Below the floor, no normal band is computed and no session is called unusual.
The numbers are still shown — withholding them would be its own kind of
dishonesty — but nothing is asserted about what is normal.

**Every definition is frozen under `BASELINE_VERSION`**, including the
thresholds above, the quantile convention, the Tukey multiplier, and the rule
that a session with no assistant turn does not count. Rows carry the version
that produced them.

The thresholds are a judgement rather than a derivation. That is exactly why
they are versioned and printed next to every answer.

## Consequences

- `atlas baseline` refuses to state a norm for three of the four projects on
  this machine. That is the correct output, not a gap to be filled in.
- Comparing a number computed under `BASELINE_VERSION` 1 with one computed
  under 2 is a mistake the schema can catch, because both carry their version.
- Later milestones inherit the floor. An intervention measured against a
  baseline that does not exist is not a measurement, so milestone 6 has to
  handle "not enough sessions to tell yet" as a first-class outcome.

## What would justify revisiting

Evidence about the distributions. The thresholds are stand-ins for a real
answer to "how many sessions before the median stops moving", and that question
is answerable from data once enough of it exists: take a project with 50
sessions, compute the running median, and see where it settles. Until then,
5 and 12 are honest guesses labelled as such.
