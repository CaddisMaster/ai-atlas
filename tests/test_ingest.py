"""Ingest acceptance tests.

The first test is the one that matters: subagent transcripts live one directory
deeper than main sessions, and the hand-written analysis that started this
project silently dropped 4 of 22 files by globbing two levels. That bug is the
reason this package exists, so it gets a test of its own.
"""

import json

from atlas.ingest import ingest
from atlas.paths import transcript_files


def test_finds_subagent_transcripts_at_any_depth(fake_home):
    found = transcript_files(fake_home)
    assert len(found) == 2, "a two-level glob would find only the main session"
    assert any("subagents" in str(p) for p in found)


def test_sessions_are_classified_by_kind(conn, fake_home):
    ingest(conn, fake_home)
    rows = {r["kind"]: r["n"] for r in
            conn.execute("SELECT kind, COUNT(*) n FROM sessions GROUP BY kind")}
    assert rows == {"main": 1, "subagent": 1}

    sub = conn.execute("SELECT * FROM sessions WHERE kind = 'subagent'").fetchone()
    assert sub["parent_session_id"] == "aaaa1111"


def test_messages_tool_calls_and_usage_land(conn, fake_home):
    ingest(conn, fake_home)
    assert conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"] == 3
    names = [r["name"] for r in conn.execute("SELECT name FROM tool_calls ORDER BY name")]
    assert names == ["Bash", "Grep", "Read"]
    u = conn.execute("SELECT * FROM usage").fetchone()
    assert u["cache_read"] == 900


def test_unmodelled_record_types_are_counted_not_dropped(conn, fake_home):
    ingest(conn, fake_home)
    row = conn.execute(
        "SELECT * FROM record_types WHERE type = 'brand-new-record-type-from-the-future'"
    ).fetchone()
    assert row is not None and row["known"] == 0 and row["count"] == 1


def test_reingest_is_idempotent(conn, fake_home):
    ingest(conn, fake_home)
    before = conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"]
    second = ingest(conn, fake_home)
    after = conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"]
    assert before == after
    assert second.bytes_read == 0, "nothing changed, so nothing should be re-read"


def test_appended_lines_cost_only_the_new_bytes(conn, fake_home, main_transcript):
    ingest(conn, fake_home)
    target = main_transcript
    with target.open("a") as fh:
        fh.write(json.dumps({
            "type": "user", "uuid": "u2", "sessionId": "aaaa1111",
            "timestamp": "2026-08-20T10:02:00Z", "message": {"role": "user", "content": "more"},
        }) + "\n")

    res = ingest(conn, fake_home)
    assert res.files_read == 1
    assert res.bytes_read < 300, "should read the appended line only, not the whole file"
    assert conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"] == 4


def test_truncation_forces_a_full_reread(conn, fake_home, main_transcript):
    ingest(conn, fake_home)
    target = main_transcript
    target.write_text(json.dumps({
        "type": "user", "uuid": "u9", "sessionId": "aaaa1111",
        "timestamp": "2026-08-20T11:00:00Z", "message": {"role": "user", "content": "rotated"},
    }) + "\n")

    res = ingest(conn, fake_home)
    assert res.bytes_read > 0, "a shrunken file must invalidate the watermark"


def test_partial_final_line_is_left_for_next_run(conn, fake_home, main_transcript):
    """A session still being written ends mid-line. We must not consume it."""
    target = main_transcript
    with target.open("a") as fh:
        fh.write('{"type": "user", "uuid": "u3", "sessionId": "aaaa1111"')  # no newline

    ingest(conn, fake_home)
    assert conn.execute("SELECT COUNT(*) n FROM messages WHERE uuid = 'u3'").fetchone()["n"] == 0

    with target.open("a") as fh:
        fh.write(', "message": {"role": "user"}, "timestamp": "2026-08-20T10:03:00Z"}\n')

    ingest(conn, fake_home)
    assert conn.execute("SELECT COUNT(*) n FROM messages WHERE uuid = 'u3'").fetchone()["n"] == 1


def test_subagent_identity_comes_from_the_path_not_the_record(conn, fake_home):
    """A subagent record carries its parent's sessionId.

    Trusting that field merges the subagent into the parent and — depending on
    which file is read first — relabels the parent as a subagent. Found on the
    first run against real transcripts, where all four subagent files carried
    their parent's id.
    """
    ingest(conn, fake_home)

    parent = conn.execute("SELECT * FROM sessions WHERE id = 'aaaa1111'").fetchone()
    assert parent["kind"] == "main", "the parent must not be relabelled by its own subagent"

    sub = conn.execute("SELECT * FROM sessions WHERE kind = 'subagent'").fetchone()
    assert sub["id"] == "agent-b222", "identity must come from the filename"
    assert sub["parent_session_id"] == "aaaa1111"

    # The subagent's tool call must be attributed to the subagent, not the parent.
    owner = conn.execute("SELECT session_id FROM tool_calls WHERE name = 'Grep'").fetchone()
    assert owner["session_id"] == "agent-b222"


def test_sessions_record_the_project_root_they_ran_in(conn, fake_home, fake_project):
    """Config is per project, so a session has to know which directory it ran in.

    The name under `projects/` cannot be decoded — dashes stand for both a
    separator and a literal dash — so the root comes from the record's `cwd`,
    confirmed by encoding it back. Here `cwd` is a subdirectory on one record,
    which is what a session that ran a command deeper in the tree looks like.
    """
    ingest(conn, fake_home)
    roots = {r["kind"]: r["project_root"] for r in
             conn.execute("SELECT kind, project_root FROM sessions")}
    assert roots == {"main": str(fake_project), "subagent": str(fake_project)}
