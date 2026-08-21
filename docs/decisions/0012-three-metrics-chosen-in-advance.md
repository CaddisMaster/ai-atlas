# 0012 — Three metrics, chosen in advance

**Status:** accepted, 2026-08-21. Amends the numbers in
[0008](0008-an-experiment-that-could-not-have-worked.md).

## Context

`0008` established that a comparison can be impossible before the data is
looked at, and measured the threshold: with thirteen metrics tested and the
significance threshold corrected for all of them, **eight sessions either side**
were needed before any verdict was reachable.

Eight either side is sixteen sessions around a single change, with no other
change in between to confound it. The best-covered project in the corpus this
was written against has ten sessions in total, over a week. So the honest
summary of milestone 6 was that the tool measured more carefully than the
available data could support — the correction was eating the evidence.

The correction is not the problem. Testing thirteen metrics at p < 0.05 turns up
one by chance, and reporting that one as a finding is exactly the failure this
project exists to avoid. The problem is testing thirteen metrics.

```
metrics tested   threshold   first reachable split
     13           0.0038          8 vs 8
      5           0.0100          8 vs 8
      3           0.0167          6 vs 6
      1           0.0500          5 vs 5
```

## Decision

**Three metrics are pre-registered**, fixed in code and frozen under
`INTERVENTION_VERSION`:

| metric | what it stands for |
|---|---|
| `duration_min` | how long a session takes |
| `user_turns` | how much steering the human had to do |
| `tools_per_turn` | how much the assistant got done per turn |

One measure of each thing an intervention plausibly changes. `tool_calls` and
`assistant_turns` are deliberately absent — they are close to linear in
duration, so testing them adds correction without adding evidence. Token counts
move with model and context behaviour more than with anything a person changes.

**Everything else is still measured and still shown**, with its before and
after, and marked `not pre-registered`. No p-value is computed for it.

The distinction that makes this legitimate: choosing metrics *before* looking is
study design; choosing them *after* seeing which moved is manufacturing a
result. Withholding the others entirely would hide context; giving them
p-values would invite the second thing.

## Consequences

- Six sessions either side, twelve around a change, instead of sixteen. Still
  ambitious for a ten-session project, but reachable rather than theoretical.
- `INTERVENTION_VERSION` is 2. Results computed under 1 corrected for thirteen
  metrics and are not comparable with these — which is exactly what the version
  is for.
- If an untested metric moves dramatically, that is visible on the screen and
  cannot be reported as a finding. Promoting it means changing
  `PREREGISTERED` — a version bump, a changelog entry, and every past result
  marked as computed under the old definition. That cost is the safeguard.

## What would justify revisiting

A paired design, which changes the arithmetic entirely: comparing within
sessions needs far fewer of them, and the metric budget can widen again without
the correction eating the evidence. That is item 1 in `status.md`.
