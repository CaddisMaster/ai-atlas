# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
described in [VERSIONING.md](VERSIONING.md).

## [Unreleased]

### Added — milestone 2, config resolution

- `python -m atlas config` resolves configuration across **six scopes** —
  enterprise, cli, local, project, user and dynamic — and reports every subagent,
  slash command, skill, hook, MCP server, memory file, setting and permission
  rule with the scope and file it came from. On the machine this was written
  against it finds, for one project, 4 subagents, 1 slash command, 1 skill, a
  `Stop` hook and 30 permission rules. `~/.claude/settings.json` contains none of
  them, and reading it alone is what produced the false findings in
  `docs/disproven.md`.
- `unknown` is a state distinct from `absent`. A managed policy that cannot be
  read, a settings file that does not parse, and a file that is not there are
  three different answers. Command-line flags are reported as permanently
  unknown, because they are written nowhere. See `docs/decisions/0004`.
- `config_scopes` records **every path checked**, found or not — 16 per project.
  "You have never configured X" is a claim about where we looked, so where we
  looked is stored as its evidence.
- `~/.claude.json` is read as the `dynamic` scope: `allowedTools` holds the
  "always allow" answers accumulated at permission prompts, which grant
  permissions and appear in no `settings.json` in any scope.
- Config is stored as history rather than as current state, fingerprinted so an
  unchanged re-run reuses its snapshot. Tables: `config_snap`, `config_scopes`,
  `config_items`, `rules`.
- Sessions record the project root they ran in, taken from each record's `cwd`.
- `python -m atlas config --all` summarises every project seen in the
  transcripts.
- 17 more tests, including the regression for the wrong answer that started the
  project: a user-scope-only read reporting no hooks, permissions, skills or
  slash commands.

### Added — milestone 1, ingest

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

- `test.sh` prefers `.venv/bin` over `PATH`. Unlike the sibling projects this one
  does not run inside a container, so bare `ruff` and `pytest` resolve to
  whatever the shell happens to have — usually nothing. It now fails with the
  venv-creation command instead of "command not found".
- Subagent transcripts are found. They live one directory deeper than main
  sessions, and the hand-written analysis that motivated this project dropped
  4 of 22 files by globbing two levels. See `docs/disproven.md`.
- Subagent session identity comes from the file path. The `sessionId` field
  inside a subagent transcript is **the parent's**, which merged subagents into
  their parent and relabelled the parent. See `docs/gotchas.md`.
- Watermark prefix hashing is capped at bytes already consumed. Hashing a fixed
  4 KB window meant any file smaller than that invalidated its own watermark on
  every append.

### Changed

- `PARSER_VERSION` is now 2 — sessions carry `project_root`, so rows produced by
  v1 are not comparable and re-ingest is forced. The database gains the column
  automatically; below 1.0 anything needing data moved is still a rebuild
  (VERSIONING.md).
- Test fixtures carry `cwd` on transcript records, including one from a
  subdirectory, because real records do and the project root is derived from it.
