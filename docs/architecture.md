# Architecture

## Shape

```
~/.claude/  ──read-only──▶  atlas.ingest  ──▶  SQLite  ──▶  (web UI, later)
   │                                                │
   ├─ projects/**/*.jsonl   transcripts             └─ ~/.local/share/ai-atlas/
   ├─ settings.json         config, user scope
   ├─ file-history/         edit before/after        git + gh ──┐
   └─ history.jsonl         prompt history                      └─▶ reconciliation
```

Three properties do most of the work:

**The filesystem is the source of truth.** Nothing pushes to us. A hook can ring
the doorbell so the database is fresh the moment a session ends, but correctness
never depends on the hook firing. See `decisions/0003`.

**Transcripts are append-only JSONL.** So a byte offset is a complete watermark,
and catching up costs new bytes only. A 49 MB transcript that grew by 40 KB
costs 40 KB.

**Session identity comes from the path, not the record.** Subagent transcripts
carry their *parent's* `sessionId`. See `gotchas.md`.

## Ingest

Per file we keep `(inode, size, last_offset, prefix_hash, parser_version)`.
Three things force a full re-read: the file shrank, the inode changed, or the
already-consumed prefix changed. Those cover rotation, compaction and
replacement.

A transcript being written right now ends mid-line. Ingest stops at the last
complete line and leaves the watermark before the partial one, so an active
session is safe to read at any moment.

## Tables

| Table | Holds |
|---|---|
| `files` | ingest watermarks |
| `sessions` | one row per transcript, `kind` = main or subagent |
| `messages` | user and assistant turns |
| `tool_calls` | one row per `tool_use` block |
| `usage` | token counts per assistant message |
| `record_types` | every record type seen, modelled or not |
| `config_snap` | one resolution of configuration, fingerprinted |
| `config_scopes` | every place looked, and what was found there |
| `config_items` | agents, commands, skills, hooks, settings, memory, mcp |
| `rules` | permission rules, split into tool and argument |
| `handoff_snap` | one reconciliation of a status document against its repo |
| `handoff_findings` | what was claimed, what was true, and where |
| `baselines` | one norm for one project and session kind |
| `baseline_metrics` | quartiles and the normal band, per metric |
| `baseline_outliers` | sessions outside the band, and on which metric |
| `baseline_exclusions` | sessions left out, and why |
| `session_metrics` | the per-session measurement itself |

Not yet built: `edits`, `classifications`, `interventions`. See `status.md`.

## Config resolution

```
enterprise  /etc/claude-code/managed-settings.json   ─┐
cli         (flags — unreadable, always unknown)      │  precedence,
local       <project>/.claude/settings.local.json     │  highest first
project     <project>/.claude/settings.json           │
user        ~/.claude/settings.json                   │
dynamic     ~/.claude.json  (always-allow answers)   ─┘
```

Plus the file-shaped scopes: `agents/*.md`, `commands/**/*.md`,
`skills/*/SKILL.md`, `CLAUDE.md` and `CLAUDE.local.md`, at both project and user
level.

Settings, agents, commands and skills **shadow** — the highest scope wins and
the losers are kept and marked. Permission rules, hooks, MCP servers and memory
files **accumulate**. A scope that cannot be read is `unknown`, never `absent`,
and every path looked at is recorded whether or not anything was found there.
See `decisions/0004`.

Which project a session ran in comes from the `cwd` on its records: the
directory name under `projects/` is a lossy encoding and is matched, never
decoded. See `gotchas.md`.

## Handoff

```
docs/status.md ──claims──▶  date · milestones · versions · test count · links
                                    │
git · CHANGELOG.md · pytest ──facts──┘  →  stale | ok | unknown, each with a line ref
```

Every check counts or compares; none of them judge. A check whose evidence
could not be gathered reports `unknown` — pytest missing is not a test count
that disagrees. Findings carry `file:line` so the reader can overrule them.

`--github` adds open pull requests and is the only network call in the project.
Offline by default; see `decisions/0005`.

## Baselines

```
sessions ──eligible?──▶ per-session metrics ──quartiles──▶ normal band
   │  no assistant turn                                        │
   └──▶ baseline_exclusions (recorded, never dropped)           ▼
                                                     outliers, if n ≥ 5
```

Metrics are per session, never pooled across the project: pooled counts let the
longest session define "normal". Each metric carries its own `n`, so a session
missing one value is absent from that metric and present in the rest.

Confidence comes from the number of sessions alone, and below five no band is
computed and nothing is called unusual — three of the four projects on this
machine do not have enough history to have a normal. See `decisions/0006`.

Every definition is frozen under `BASELINE_VERSION`, separately from
`PARSER_VERSION`: one says what the transcript said, the other says what we made
of it.

## What is deliberately absent

**No server, no container, no Postgres.** The product only works if a stranger
can clone it and see a number two minutes later. See `decisions/0002`.

**No network.** Ingest is stdlib-only and entirely offline. See `SECURITY.md`.
