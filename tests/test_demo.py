"""Demo acceptance tests.

The demo is the first place a fixture becomes a product, so it is held to the
faithfulness rules in `docs/testing.md` and to one more: **it must not flatter
the tool**. A demo where every baseline is confident and every intervention has
a verdict would misrepresent what this does with ten real sessions, so a test
asserts that some of the generated comparisons come back refused.
"""

import json

from atlas.baseline import build
from atlas.config import resolve
from atlas.demo import BUILD, MARKER, NOISE, RITUAL, generate
from atlas.ingest import ingest
from atlas.interventions import MOVED, NO_VERDICT, NOT_TESTED, TOO_FEW, measure, record
from atlas.patterns import find

VOCABULARY = {word.split()[0] for word in (*RITUAL, *NOISE, *BUILD)} | {"cd", "echo"}


def _corpus(tmp_path, name="demo", **kw):
    return generate(tmp_path / name, **kw)


def _transcripts(corpus):
    return sorted(corpus.claude_home.rglob("*.jsonl"))


def test_the_same_seed_gives_the_same_corpus(tmp_path):
    """A screenshot in the README has to be reproducible by a stranger."""
    first = _corpus(tmp_path, "a", sessions=6)
    second = _corpus(tmp_path, "b", sessions=6)

    def shape(corpus):
        return [(p.name, len(p.read_text().splitlines())) for p in _transcripts(corpus)]

    assert shape(first) == shape(second)
    assert shape(_corpus(tmp_path, "c", seed=1, sessions=6)) != shape(first)


def test_nothing_in_the_corpus_is_a_recording(tmp_path):
    """Every command is built from the demo's own invented vocabulary.

    A demo assembled from somebody's real transcripts would carry their source
    code, their hostnames and their shell output — which is the entire reason
    this project generates one instead.
    """
    corpus = _corpus(tmp_path, sessions=6)
    commands = []
    for path in _transcripts(corpus):
        for line in path.read_text().splitlines():
            try:
                record_ = json.loads(line)
            except json.JSONDecodeError:
                continue          # the deliberately truncated final line
            for block in (record_.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    command = (block.get("input") or {}).get("command")
                    if command:
                        commands.append(command)

    assert commands
    for command in commands:
        for segment in command.replace("&&", "\n").splitlines():
            head = segment.split()[0] if segment.split() else ""
            assert head in VOCABULARY, f"{head!r} is not from the demo vocabulary"


def test_the_awkward_cases_are_all_present(conn, tmp_path):
    """The corpus contains what a real one contains, on purpose."""
    corpus = _corpus(tmp_path, sessions=8)
    result = ingest(conn, corpus.claude_home)

    kinds = dict(conn.execute("SELECT kind, COUNT(*) FROM sessions GROUP BY kind").fetchall())
    assert kinds["subagent"] >= 1, "a subagent transcript, one level deeper"

    subagent = conn.execute("SELECT * FROM sessions WHERE kind = 'subagent'").fetchone()
    parent = conn.execute("SELECT * FROM sessions WHERE id = ?",
                          (subagent["parent_session_id"],)).fetchone()
    assert parent and parent["kind"] == "main", "carrying its parent's sessionId, as real ones do"

    assert "demo-only-record" in result.unknown_types, "an unmodelled type to count"

    abandoned = build(conn, str(corpus.projects[0])).excluded
    assert abandoned, "sessions typed and walked away from"

    last = max(_transcripts(corpus), key=lambda p: p.stat().st_mtime)
    assert not last.read_text().endswith("\n"), "the live one ends mid-record"


def test_the_truncated_transcript_is_not_consumed(conn, tmp_path):
    corpus = _corpus(tmp_path, sessions=6)
    ingest(conn, corpus.claude_home)

    live = max(_transcripts(corpus), key=lambda p: p.stat().st_mtime)
    row = conn.execute("SELECT last_offset FROM files WHERE path = ?", (str(live),)).fetchone()
    assert row["last_offset"] < live.stat().st_size, "the half-written record is left for later"


def test_every_scope_has_something_to_say(tmp_path):
    """Including the one nobody looks for: an "always allow" answer in
    ~/.claude.json, which appears in no settings.json anywhere."""
    corpus = _corpus(tmp_path, sessions=4)
    resolution = resolve(corpus.projects[0], root=corpus.claude_home,
                         enterprise=tmp_path / "no-policy.json")

    scopes = {rule.scope for rule in resolution.rules}
    assert {"project", "user", "dynamic"} <= scopes
    assert {item.kind for item in resolution.items} >= {"agent", "command", "skill", "hook"}


def test_one_project_is_measurable_and_one_is_refused(conn, tmp_path):
    """Not tuned to flatter: the small project gets told it has no normal."""
    corpus = _corpus(tmp_path, sessions=20)
    ingest(conn, corpus.claude_home)
    busy, tiny = corpus.projects

    assert build(conn, str(busy)).confidence == "established"
    assert build(conn, str(tiny)).confidence == "unknown"


def test_the_ritual_is_found_and_ranked_above_the_noise(conn, tmp_path):
    corpus = _corpus(tmp_path, sessions=20)
    ingest(conn, corpus.claude_home)

    report = find(conn, str(corpus.projects[0]))
    assert report.patterns, "the generated habit has to be findable"
    assert "Bash:git commit" in report.patterns[0].text
    assert report.patterns[0].lift > 100


def test_the_demo_shows_refusals_as_well_as_findings(conn, tmp_path):
    """The honesty test.

    The corpus has a real effect in it, so something should move. It also has
    metrics that did not move and a change too late to measure, and both have to
    be visible — otherwise the demo teaches a reader that this tool always
    produces a verdict.
    """
    corpus = _corpus(tmp_path, sessions=20)
    ingest(conn, corpus.claude_home)
    busy = str(corpus.projects[0])

    real = measure(conn, intervention_id=record(conn, busy, "the change", corpus.changed_on))
    tested = [r for r in real.results if r.verdict in (MOVED, NO_VERDICT)]
    assert MOVED in {r.verdict for r in tested}, "a real effect, and enough sessions to see it"
    assert [r for r in real.results if r.verdict == NOT_TESTED], \
        "the metrics nobody pre-registered are shown and not tested"

    late = measure(conn, intervention_id=record(conn, busy, "too late",
                                                "2027-01-01T00:00:00+00:00"))
    assert {r.verdict for r in late.results if r.verdict != NOT_TESTED} == {TOO_FEW}


def test_the_directory_is_marked_as_disposable(tmp_path):
    """`--fresh` deletes a directory, so it checks for this first."""
    corpus = _corpus(tmp_path, sessions=3)
    assert (corpus.root / MARKER).exists()
