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

## Format

Each record states the context, the decision, its consequences, and — most
importantly — **what would justify revisiting it**. A decision with no stated
reversal condition is dogma rather than engineering.

New records get the next number and a row in the table above. Superseded records
are kept and marked, never deleted.
