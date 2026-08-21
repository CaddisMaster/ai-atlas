# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
described in [VERSIONING.md](VERSIONING.md).

## [Unreleased]

### Added — milestone 7, now

- `python -m atlas now` reports what is happening in the session being written
  right now: turns, tool calls, the last few things it did, and where the
  session sits among that project's past sessions. `--watch N` refreshes.
- The live transcript is found by **file mtime, not by querying the database** —
  a session that started ten seconds ago has no rows yet.
- Looking costs **new bytes only**: `ingest_one` catches up on a single file
  through the milestone-1 watermark. Watching this repository's own session read
  313 KB on the first look and 0 on the second.
- **A live session is n = 1**, so the screen states facts and places them, and
  never grades. No score, no severity, no advice — and `Placement` has no field
  for one, with a test asserting those fields do not exist. Below five past
  sessions nothing is placed at all and the raw counts are still shown. See
  `docs/decisions/0009`.
- Nothing about the live view is stored. It is the one genuinely ephemeral thing
  here; the rows behind it are already in the database.
- `test_ingest_keeps_up_with_a_live_writer` closes the gap `docs/testing.md` has
  listed since milestone 1: a thread appending records **in fragments** while
  the reader catches up, asserting every record arrives exactly once.

### Fixed

- `atlas now --watch` flushes each frame. Redirected stdout is block-buffered,
  so a watch piped to a file produced nothing at all until the buffer filled —
  and nothing ever, if it was interrupted first.

### Added — milestone 6, interventions

- `python -m atlas intervention add` records a change to how you work with its
  date and, in your own words, what you were hoping for. The expectation is
  stored and **never scored** — checking whether the numbers agree with what
  somebody already believed is the trap this subsystem exists to avoid.
- `python -m atlas intervention detect` proposes changes from two sources:
  differences between stored config snapshots (exact about what, vague about
  when) and config file mtimes (exact about when, silent about what). Four real
  changes were found inside the period the corpus covers.
- `python -m atlas intervention list` splits a project's sessions by the date
  and compares them on the metrics milestone 4 already stores, with an **exact
  permutation test** — every relabelling enumerated, no distributional
  assumption, no sampling, no seed at these sizes.
- **Four outcomes, not two.** Beyond `moved` and `no verdict`, there is
  `not enough sessions` and — the one that matters —
  `cannot separate at this sample size`. Three sessions against three cannot
  produce a p below 0.2 however cleanly the data separates, so the tool computes
  the floor the split sizes admit *before* looking at the data and says when no
  arrangement could have cleared the threshold. Eight sessions either side, at
  thirteen metrics. See `docs/decisions/0008`.
- The threshold is corrected for the number of metrics tested, and the
  uncorrected p-value is printed next to it. Thirteen metrics at p < 0.05 turns
  up one by chance.
- A session in flight when a change landed belongs to neither side, and is
  reported rather than assigned.
- `INTERVENTION_VERSION` freezes the comparison rules. A result carries it *and*
  `BASELINE_VERSION`, because it depends on how the metrics were computed as
  well as on how they were compared.
- 14 more tests, most of them about the refusals.

### Added — milestone 5, patterns

- `python -m atlas patterns` finds tool sequences that repeat across sessions,
  shows the session and message each occurrence started at so the claim can be
  checked by hand, and proposes the artifact that fits its shape — a slash
  command, or a hook when the sequence keeps landing at the end of a session.
- **Every tool call carries a signature**: the first two meaningful words of a
  shell command, the extension of a file touched, the name of a skill invoked.
  198 distinct signatures where there were 20 tool names. 89% of calls in the
  corpus are `Bash`, so the tool name alone cannot show repetition.
  `PARSER_VERSION` is now 3.
- **Ranking is by lift, never frequency.** The most common pair in the corpus,
  `grep → sed` in 8 sessions, scores 2.0 — what chance predicts. The release
  ritual `git add → git push → gh pr` scores 249 on four occurrences. Ranking by
  frequency buried every real pattern. See `docs/decisions/0007`.
- Consecutive repeats are collapsed before mining: the number of greps in a row
  varies, the shape is what repeats. A run of one call can therefore never be
  reported as a sequence — repetition is a permission question instead.
- A signature used often that no allow rule in any scope covers is a permission
  proposal, with the rule that would cover it. With no resolved config to check
  against, **no claim is made** — "no rule covers this" is a claim about every
  scope, which is what milestone 2 exists to get right.
- A command line never reaches the database. `SECURITY.md` guarantee 4 is new
  and says so.
- `PATTERN_VERSION` freezes the thresholds, the lift floor, the collapsing rule
  and the subsumption rule.
- 32 more tests, including the signature cases copied out of real commands.

### Fixed — found by running over 2,780 real tool calls

- Multi-line commands are split correctly. A third of real commands look like
  `cd /path\nsed …`, and splitting on `&&`, `;` and `|` but not `\n` left the
  `cd` in front of everything: 48 calls landed in a bucket named `?`.
- `echo "=== x ==="; tmux capture-pane` signs as `tmux capture-pane`. An echo in
  front of a command is a label, not the work.
- `pattern_occurrences` is keyed on the position in the session, not the message
  uuid. One assistant message can make several tool calls, so two occurrences of
  a sequence can start in the same message.

### Added — milestone 4, baselines

- `python -m atlas baseline` states what a normal session looks like in one
  project: duration, turns, tool calls, tools per turn, output tokens, cache hit
  rate, the largest silence inside a session, and the share of a session's own
  tool calls going to each of the top five tools. Quartiles, a Tukey normal
  band, and the sessions that fall outside it.
- **Confidence comes from the sample size, and gates what is claimed.** Below 5
  sessions no band is computed and no session is called unusual; 5–11 is
  `provisional`; 12 or more is `established`. Three of the four projects on this
  machine are told they do not have a normal yet, which is the correct answer.
  See `docs/decisions/0006`.
- `BASELINE_VERSION` freezes every definition — eligibility, the quantile
  convention, the outlier fence, the thresholds — separately from
  `PARSER_VERSION`. One says what the transcript said, the other what we made of
  it. `VERSIONING.md` covers both.
- Sessions with no assistant turn are excluded from baselines and **recorded**
  in `baseline_exclusions` with the reason. Three of thirteen real sessions in
  one project are a prompt typed and abandoned.
- Tool mix is measured per session and then summarised, never pooled across the
  project — pooling lets the longest session define "normal".
- Each metric carries its own `n`: a session missing one value is absent from
  that metric and present in the rest.
- `session_metrics` stores the per-session numbers, which is what milestone 6
  will compare before and after an intervention.
- 16 more tests, most of them about the refusals rather than the numbers.

### Fixed — caught by handoff, in this repository

- A milestone mentioned in the changelog's *prose* is no longer read as landed.
  "…which is what milestone 6 will compare" made handoff report an empty roadmap
  row as stale. Only `###` headings inside `[Unreleased]` count as a claim now.
  Found one commit after the sentence was written, by the check itself.

### Added — milestone 3, handoff

- `python -m atlas handoff` checks a status document against the repository and
  reports what has gone stale. Seven checks, every one of them deterministic:
  the as-of date against the last commit, roadmap rows against the changelog's
  `[Unreleased]` milestones, the newest release tag against whether the document
  mentions it, `N tests` against `pytest --collect-only`, relative links against
  the filesystem, code committed since the changelog was last touched, and open
  pull requests with `--github`.
- Findings carry `file:line`, so a reader can overrule one without re-deriving
  it, and are stored in `handoff_snap` / `handoff_findings` — "this has been
  wrong since Tuesday" is a question with an answer now.
- A check whose evidence could not be gathered reports `unknown`, never `ok` or
  `stale`. Missing pytest is not a test count that disagrees, and a directory
  that is not a git repository produces one honest unknown rather than seven
  confident findings.
- `--github` is the only network call in ai-atlas: opt-in per run, sends a
  repository name, sends nothing read out of `~/.claude`. `SECURITY.md`
  guarantee 1 is restated to name the data rather than the socket. See
  `docs/decisions/0005`.
- 12 more tests, including regressions for both defects found by pointing the
  new checks at a repository that was not written for them.

### Fixed — found on real data, before release

- Release tags of the form `v0.8.0` parsed as no version at all: `\b` does not
  match between `v` and a digit, so the version check crashed on the first
  repository with tags. This repository has none.
- A dependency's version is no longer compared against a git tag. The check
  compared PostgreSQL 10.15.0 with `v0.8.0` and called the document stale; it
  now asks only whether the document mentions the newest tag on the repository
  it is checking.
- A per-file test count (`` `tests/test_x.py` (10 tests) ``) is no longer read as
  a claim about the whole repository.

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
