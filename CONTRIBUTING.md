# Contributing

## Getting set up

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
./test.sh
```

Runtime has no dependencies. `requirements-dev.txt` is pytest and ruff.

## Working against your own data

`python -m atlas ingest` reads your real `~/.claude`. Two environment variables
keep experiments away from anything you care about:

```bash
ATLAS_CLAUDE_HOME=/path/to/fixture   # read somewhere else
ATLAS_DB=/tmp/scratch.db             # write somewhere else
```

Use both when trying something out. The default database is as sensitive as the
transcripts it was built from.

## Tests

Every bug gets a regression test named after what it broke, and a comment saying
how it was found. Two exist already and both were found by running against real
data rather than by reasoning — that is the expected ratio.

**Fixtures stay faithful, not convenient.** If real data has an awkward shape,
the fixture has it too.

## Adding a column or a table

Widening is safe: SQLite tolerates it, older rows keep empty cells, and
`ingest` refills what it can. Changing the *meaning* of an existing column is
not safe — that is a `PARSER_VERSION` bump, because it silently breaks every
comparison that spans the change.

## Decisions

A call that would tempt someone later to "fix" it gets a record in
`docs/decisions/`. State what would justify revisiting it; a decision with no
reversal condition is dogma rather than engineering.
