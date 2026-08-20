# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
described in [VERSIONING.md](VERSIONING.md).

## [Unreleased]

### Added

- Incremental transcript ingest into SQLite. A watermark of
  `(inode, size, last_offset, prefix_hash)` per file means re-ingest costs new
  bytes only — a second run over 52.7 MB reads 0 bytes.
- `record_types` table counting **every** record type seen, modelled or not, so
  a change to the transcript format shows up as a number rather than as missing
  data. Four unmodelled types were present on day one: `pr-link`, `atis-latch`,
  `frame-link`, `artifact-comment-monitor`.
- `python -m atlas ingest` and `python -m atlas stats`.
- Nine ingest tests, including regressions for both bugs found while writing it.

### Fixed

- Subagent transcripts are found. They live one directory deeper than main
  sessions, and the hand-written analysis that motivated this project dropped
  4 of 22 files by globbing two levels. See `docs/disproven.md`.
- Subagent session identity comes from the file path. The `sessionId` field
  inside a subagent transcript is **the parent's**, which merged subagents into
  their parent and relabelled the parent. See `docs/gotchas.md`.
- Watermark prefix hashing is capped at bytes already consumed. Hashing a fixed
  4 KB window meant any file smaller than that invalidated its own watermark on
  every append.
