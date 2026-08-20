# 0003 — The filesystem is the source of truth

**Status:** accepted, 2026-08-20

## Context

Claude Code offers hooks that can fire on session events, which makes a push
model tempting: a `Stop` hook that notifies ai-atlas the moment a session ends,
with exact event boundaries instead of boundaries inferred from a log.

The failure mode is that correctness starts depending on a hook firing. Hooks
get removed, break, sit in a scope that is not active, or fail silently. A
measurement system that quietly misses sessions is not a measurement system —
and the gaps would be invisible precisely when they matter, since a session that
was never recorded leaves nothing behind to notice.

## Decision

The filesystem is the source of truth. Ingest scans, watermarks and reads
forward, and a full scan is always sufficient to reach a correct state.

A hook may ring the **doorbell** — trigger an ingest so the database is fresh
immediately — but it never delivers data, and nothing is lost if it never fires.

## Consequences

- Ingest must be cheap enough to run often, which is what the byte-offset
  watermark buys: a second run over 52.7 MB reads 0 bytes.
- Session start and end are derived from first and last message timestamps.
  There is no "session ended" record, so this is an approximation, and any
  measurement using session duration must say so.
- The application works fine for a user who has configured nothing.

## What would justify revisiting

A transcript format that stops being append-only — compaction that rewrites
history in place, say. Byte-offset watermarking assumes append-only, and the
prefix-hash guard detects the violation but degrades to a full re-read every
time. At that point the trade changes.
