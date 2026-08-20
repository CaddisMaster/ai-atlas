# Testing

```bash
./test.sh          # ruff, then pytest
./test.sh -k name  # arguments pass through to pytest
```

## What the tests are for

Nine tests, and the two that matter most are regressions for bugs found by
running against **real data** rather than by reasoning about it:

- `test_finds_subagent_transcripts_at_any_depth` — the two-level glob that
  dropped 4 of 22 files.
- `test_subagent_identity_comes_from_the_path_not_the_record` — the parent's
  `sessionId` appearing inside a subagent transcript.

A third, `test_appended_lines_cost_only_the_new_bytes`, failed on its first run
and exposed a genuine defect: the watermark's prefix hash covered a fixed 4 KB
window, so any file smaller than that invalidated its own watermark on every
append. That is the whole argument for writing the acceptance test before
believing the implementation.

## Fixtures stay faithful, not convenient

`tests/conftest.py` builds a `~/.claude` with a main session and a subagent
beneath it. The subagent record carries the **parent's** `sessionId`, because
real ones do. A tidier fixture would have hidden the bug it now guards.

## What is not tested yet

Ingest against a transcript that is actively being written. The partial-line
path is covered synthetically, but not under a real concurrent writer.
