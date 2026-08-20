# 0002 — SQLite, not Postgres

**Status:** accepted, 2026-08-20

## Context

The two sibling projects both run Flask on Postgres in Docker, and that stack is
well understood here. The obvious move was to copy it.

But this application is meant to be cloned and run by someone who has never seen
it. Its whole argument — *you cannot see how you work with this tool* — is only
persuasive if a stranger reaches a real number quickly. A `docker compose up`
and a database container standing between them and that number is fatal to
adoption, and adoption is the point.

The workload also suits SQLite exactly: single-writer, append-mostly analytics
over tens of megabytes, read from one machine by one person.

## Decision

SQLite, in a single file at `~/.local/share/ai-atlas/atlas.db`.

Ingest is **stdlib-only**. `python -m atlas ingest` works on a clean checkout
with no install step at all.

Docker, when it arrives, is for the web UI only and stays optional.

## Consequences

- No connection strings, no migrations service, no container for the core path.
- Concurrent writers are not supported. One ingest at a time; the live watcher
  reads and never writes. This mirrors the `gfn-rig` split, where a second
  writer would have raced the agent for the same CSV.
- Losing the database is cheap while the schema is `0.x`: the source of truth is
  `~/.claude`, so a rebuild costs seconds. That stops being true at `1.0.0`,
  when measured interventions and human confirmations exist that cannot be
  re-derived. See [VERSIONING.md](../../VERSIONING.md).

## What would justify revisiting

Multi-user aggregation. If people ever opt into contributing anonymised findings
to a shared dataset, that server is a different application with a different
store — and this decision does not constrain it.
