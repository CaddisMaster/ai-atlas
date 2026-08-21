# Testing

```bash
./test.sh          # ruff, then pytest
./test.sh -k name  # arguments pass through to pytest
```

## What the tests are for

One hundred and forty-six tests. The ones that matter most are regressions for wrong answers
found by running against **real data** rather than by reasoning about it:

- `test_project_scope_is_not_missed_by_a_user_scope_read` — the false claim that
  started the project: no hooks, no permissions, no skills, no slash commands,
  all of them present one directory away.
- `test_finds_subagent_transcripts_at_any_depth` — the two-level glob that
  dropped 4 of 22 files.
- `test_subagent_identity_comes_from_the_path_not_the_record` — the parent's
  `sessionId` appearing inside a subagent transcript.
- `test_a_v_prefixed_tag_is_still_a_version` and
  `test_a_dependency_version_is_not_compared_against_a_tag` — both found by
  pointing `handoff` at the sibling project, one a crash and one a false
  "stale". This repository could not have found either: it has no tags.

Another, `test_appended_lines_cost_only_the_new_bytes`, failed on its first run
and exposed a genuine defect: the watermark's prefix hash covered a fixed 4 KB
window, so any file smaller than that invalidated its own watermark on every
append. That is the whole argument for writing the acceptance test before
believing the implementation.

`test_the_demo_shows_refusals_as_well_as_findings` guards the demo against
itself: the same measurement has to contain a `moved` **and** a `no verdict`. If
the generator is ever tuned until everything moves, that test fails.

The report tests guard two things nothing else can: that the page requests
**nothing** when opened, and that it never says about a session what the mockup
this design came from said — "going backwards", "spiral", "not holding". A list
of forbidden words is a blunt instrument and exactly right here, because the
temptation is a UI one.

The apply tests are almost entirely refusals — a symlink out of the project,
any path under `~/.claude` that is not `settings.json`, a malformed file, a
command name that is a path traversal. It is the only module that writes, so
what it declines to do is the specification.

`test_ingest_keeps_up_with_a_live_writer` closes the gap this file has listed
since milestone 1. A thread appends records **in fragments**, so the transcript
genuinely spends time ending mid-line, while the reader catches up in a loop.
Every record has to arrive exactly once, and the watermark has to finish at the
end of the file.

`test_the_reachable_floor_comes_out_of_the_sample_size` is the one to read
first. It is not a regression: it is the finding that eight sessions either side
are needed before an intervention verdict is reachable at all, pinned as a test
so that nobody quietly lowers the bar later.

The pattern tests are mostly about *not* finding things: a coincidence, a
repetition, a habit that happened once. `test_calls_that_merely_co_occur_are_not_a_pattern`
is the frequency trap that the real corpus walked into first.

Most of the baseline tests are about the **refusals** — the sample below the
floor, the abandoned session, the subagents kept out of the main baseline —
because that is where a measurement tool does damage. A median printed without
its sample size is the failure mode, and it looks like success.

## Fixtures stay faithful, not convenient

`tests/conftest.py` builds a `~/.claude` with a main session and a subagent
beneath it. The subagent record carries the **parent's** `sessionId`, because
real ones do. A tidier fixture would have hidden the bug it now guards.

`fake_project` mirrors a real project's configuration in the same spirit: the
hook path goes through `$CLAUDE_PROJECT_DIR`, the skill is a *directory* holding
`SKILL.md` rather than a file named after itself, and `~/.claude.json` sits
beside `~/.claude` rather than inside it.

One fixture is deliberately ahead of reality: `allowedTools` is populated, while
every real project on this machine has it empty. That code path has no live
data behind it, which is worth knowing when it eventually misbehaves.

## What is not tested yet

Signature extraction is tested against commands copied out of the corpus —
multi-line `cd` prefixes, `echo` labels, loop headers, `.venv/bin/pytest`. Two
of those cases are regressions for defects found by running the extractor over
2,780 real calls, before any of it was wired into ingest.

Baseline fixtures build database rows rather than transcripts. The JSONL path
into those tables is covered by the ingest tests, and duplicating it here would
test the fixture rather than the measurement — but it does mean a change to
ingest's column semantics could pass these tests. The shapes are copied from the
corpus, including sessions with no assistant turn.

`handoff --github`. It is the one code path that needs the network, so it is
the one path the test suite cannot exercise. Everything it does offline is
tested; the `gh` call itself is not.

Enterprise managed policy with actual content. No such file exists on this
machine, so the tests cover "unreadable" and "absent" but never a policy whose
rules have to be merged with the rest.

Plugins. `~/.claude/plugins/` is not read at all yet — see `status.md`.
