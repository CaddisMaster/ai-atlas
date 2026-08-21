# Security and data handling

This application reads the most sensitive directory on a developer's machine.
That is not an overstatement, and the design follows from it.

## What is in the data

- **Source code**, in full, for every file Claude Code has read or written.
- **Shell output**, which routinely contains tokens, connection strings and
  environment variables that were never meant to be persisted.
- **`~/.claude/settings.json`**, which on the machine this was written against
  contains droplet hostnames, deploy paths, secret *names*, and a description of
  where sensitive data lives.
- **Employer data**, for anyone who uses Claude Code at work.

## The guarantees

1. **Nothing is transmitted.** ai-atlas makes no outbound network calls. There
   is no telemetry, no crash reporting, and no "anonymous usage statistics".
2. **Nothing in `~/.claude` is written to.** Every access is read-only. The
   application has its own database elsewhere and never modifies the source.
3. **The database is local.** `~/.local/share/ai-atlas/atlas.db` by default.
   It is as sensitive as the transcripts it was built from — back it up with
   the same care, or not at all.
   Config snapshots keep settings **values**, which is where the droplet
   hostnames and secret names above live. Only the first 200 characters plus a
   hash are stored — enough to see a value change, not a second copy of
   everything — but that is a reduction in exposure, not an absence of it.
4. **`.gitignore` refuses `*.db`**, and `/scratch/` and `/exports/` alongside
   it. Nothing read out of `~/.claude` belongs in this repository.

## When a model is involved

Later milestones classify message content with a model, which means sending
excerpts to an API. That crosses guarantee 1, so it must be:

- **off by default**, and enabled explicitly per project;
- **scoped** — the smallest excerpt that answers the question, never a whole
  session;
- **logged** — every call recorded with its cost, so the bill is inspectable;
- **cached by content hash**, so the same text is never sent twice.

Until that lands, ai-atlas is entirely offline.

## Reporting

Personal project, no formal process. Open an issue.
