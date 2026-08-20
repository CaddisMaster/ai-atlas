# Gotchas

Things that cost time once. Each is load-bearing somewhere in the code.

## Subagent transcripts sit one level deeper

```
projects/<project>/<session>.jsonl                        main
projects/<project>/<session>/subagents/agent-<id>.jsonl    subagent
```

A glob of `*/*.jsonl` finds main sessions only. It dropped 4 of 22 files —
1.0 MB, every subagent run — in the analysis that motivated this project.
Use `rglob`. Guarded by a test.

## A subagent's `sessionId` is its parent's

All four subagent transcripts on the machine this was written against carry the
parent session's id, not their own. Keying session identity on that field merges
the subagent into its parent and — depending on which file is read first —
relabels the parent as a subagent.

**Identity comes from the file path.** `path.stem` for subagents, the record's
`sessionId` for main sessions.

## The watermark's prefix hash must cover consumed bytes only

Hashing a fixed 4 KB window means any transcript smaller than 4 KB changes its
own hash every time a line is appended, invalidating its watermark and forcing a
full re-read — for exactly the small, actively-growing files where incremental
ingest matters most. Cap the hash length at `min(PREFIX_BYTES, last_offset)`.

## An active transcript ends mid-line

A session being written right now has an incomplete final line. Consuming it
loses the record when the rest arrives. Stop at the last complete line and leave
the watermark before the partial one.

## Unmodelled record types appear without warning

Present on day one and not in any documentation: `pr-link` (438),
`atis-latch` (225), `frame-link` (20), `artifact-comment-monitor` (3). They are
counted in `record_types` with `known = 0`. Check that table after any Claude
Code update — it is the drift alarm.

## `test.sh` must prefer `.venv/bin` over `PATH`

Unlike the sibling projects, this one does not run inside a container, so bare
`ruff` and `pytest` resolve to whatever the shell happens to have — usually
nothing. The script checks `.venv/bin` first and fails with the venv-creation
command rather than a bare "command not found".
