# Architecture decision records

One record per call that is **locked** — a decision where the reasoning matters
more than the outcome, and where someone arriving later would otherwise be
tempted to "fix" it.

These are not a log of everything ever decided. That is what
[CHANGELOG.md](../../CHANGELOG.md) and git history are for. An ADR earns its
place when the decision is counter-intuitive, when it was reached the hard way,
or when reversing it would break something non-obvious.

| # | Decision | Short version |
|---|---|---|
| [0001](0001-config-resolves-across-all-scopes.md) | Config resolves across all scopes | Reading one scope and reporting on all of them produces confident lies |
| [0002](0002-sqlite-not-postgres.md) | SQLite, not Postgres | A container between a stranger and their first number is fatal |
| [0003](0003-filesystem-is-the-source-of-truth.md) | The filesystem is the source of truth | Hooks are a doorbell, never a delivery mechanism |
| [0004](0004-a-scope-we-cannot-read-is-unknown.md) | A scope we cannot read is unknown | Absent, refused and malformed are three answers, not one |
| [0005](0005-offline-by-default-github-is-opt-in.md) | Offline by default, GitHub opt-in | The promise is about the data, not the socket |
| [0006](0006-a-norm-needs-a-floor.md) | A norm needs a floor | Three sessions is arithmetic, not a normal |
| [0007](0007-lift-not-frequency.md) | Lift, not frequency | The most common pair in the corpus means nothing |
| [0008](0008-an-experiment-that-could-not-have-worked.md) | "Could not have found anything" ≠ "found nothing" | Three against three cannot beat p = 0.2, whatever happened |
| [0009](0009-a-live-session-is-n-of-one.md) | A live session is n = 1 | State the fact, place it, never grade it |
| [0010](0010-writing-is-narrowed-not-excepted.md) | Writing is narrowed, not excepted | The protected thing is the record, not the directory |
| [0011](0011-the-demo-must-not-flatter-the-tool.md) | The demo must not flatter the tool | An accurate advertisement, not a good one |
| [0012](0012-three-metrics-chosen-in-advance.md) | Three metrics, chosen in advance | The correction was eating the evidence |

## Format

Each record states the context, the decision, its consequences, and — most
importantly — **what would justify revisiting it**. A decision with no stated
reversal condition is dogma rather than engineering.

New records get the next number and a row in the table above. Superseded records
are kept and marked, never deleted.
