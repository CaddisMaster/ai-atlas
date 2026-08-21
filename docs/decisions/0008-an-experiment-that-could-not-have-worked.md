# 0008 — "Could not have found anything" is a different answer from "found nothing"

**Status:** accepted, 2026-08-21. The sample sizes below were measured against
thirteen metrics; [0012](0012-three-metrics-chosen-in-advance.md) cuts that to
three and the figure to six either side. The reasoning is unchanged.

## Context

Milestone 6 compares sessions before a change with sessions after it. The
comparison is an exact permutation test: of all the ways these sessions could
have been split into two groups of the same sizes, how many separate the medians
at least as far as the real split did?

Writing the test for three sessions against three produced a p-value of 0.2 on
data that was *perfectly* separated — 500 minutes against 1 minute. That is not
a bug. Three against three has twenty relabellings, and four of them always tie
with the real one. **0.2 is the smallest p-value that shape can produce**,
whatever the sessions did.

Measuring the rest:

```
3 vs 3   floor 0.200        6 vs 6   floor 0.013
4 vs 4   floor 0.057        7 vs 7   floor 0.012
5 vs 5   floor 0.048        8 vs 8   floor 0.0031   ← first to clear 0.05 ÷ 13
```

With thirteen metrics and a threshold corrected for them, **eight sessions
either side** — sixteen around the change — are needed before any verdict is
reachable at all. The best-covered project in the corpus has ten sessions in
total.

Reporting "no verdict" in that situation is a lie of omission. It reads as *the
change did not do anything*, when the truth is *this experiment could not have
detected anything, including a large effect*.

## Decision

The tool computes the **smallest p-value the split sizes admit**, by running the
same permutation test on a perfectly separated sample of the same shape, and
compares it against the threshold before looking at the data.

When the floor is above the threshold, the verdict is `cannot separate at this
sample size` — a distinct outcome from `no verdict`, stored distinctly, and
explained in the output: *"6 against 4 cannot produce a p below 0.013 however
the sessions fell, and the threshold is 0.0038."*

`atlas intervention detect` prints how many sessions currently sit either side
of each candidate change, and states the eight-a-side figure up front. The point
is to be known before an experiment, not after it.

## Consequences

- Most real interventions on this corpus return `not enough sessions` or
  `cannot separate`. That is the honest state of the evidence, and the tool's
  job is to say so rather than to produce a number per intervention.
- The eight-a-side figure follows from the metric count. Testing fewer metrics
  raises the threshold and lowers the bar — but choosing metrics *after* seeing
  which ones moved is the oldest way to manufacture a result, so the metric set
  stays fixed and frozen under `BASELINE_VERSION`.
- Recording an intervention is still worth doing on day one, because the
  after-half only starts accumulating once it is recorded.

## What would justify revisiting

A paired design. Comparing whole sessions treats them as interchangeable, which
they are not; a comparison *within* sessions — the same task before and after,
or the same hour of the day — would need far fewer of them. That is a real
improvement available later, and it needs its own definition of "the same task",
which is exactly the kind of thing that has to be versioned rather than tuned.
