"""Live-session acceptance tests.

Two things are being checked here, and they are unrelated except that this
milestone is where both come due.

The first is restraint. A live session is n = 1, so the screen may state facts
and place them among past sessions, and may not imply a judgement. There is no
score and no severity anywhere in the data structures, which is deliberate:
something that does not exist cannot be printed by accident.

The second is the partial-line path in ingest, which has been covered
synthetically since milestone 1 and never run against a real concurrent writer.
`test_ingest_keeps_up_with_a_live_writer` is that test, with a thread appending
records in fragments while the reader repeatedly catches up.
"""

import json
import os
import threading
import time

import pytest

from atlas.ingest import ingest, ingest_one
from atlas.now import live_transcripts, look
from tests.conftest import add_session


def _stamp(path, seconds_ago):
    """Pin an mtime, so "which transcript is live" is decided by the test.

    The fixture's subagent transcript is written after its parent and is
    therefore the newer file — a fine reflection of reality, and a terrible
    thing to leave implicit in a test about picking the newest.
    """
    when = time.time() - seconds_ago
    os.utime(path, (when, when))


def _live_is_the_main_session(fake_home, main_transcript):
    """Make the main transcript the most recently written one."""
    for path in fake_home.rglob("*.jsonl"):
        _stamp(path, 300)
    _stamp(main_transcript, 1)


def _record(n):
    return {"type": "assistant", "uuid": f"live{n}", "sessionId": "aaaa1111",
            "cwd": "/work/demo-app", "timestamp": f"2026-08-20T10:{n:02d}:00Z",
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": "Bash",
                                     "input": {"command": "git status"}}]}}


def test_nothing_running_is_a_valid_answer(conn, fake_home):
    """The usual state of affairs, and it must not look like an error."""
    assert look(conn, fake_home, within_minutes=0) is None


def test_the_live_transcript_is_the_one_most_recently_written(fake_home, main_transcript):
    subagent = next(p for p in fake_home.rglob("*.jsonl") if "subagents" in str(p))
    _stamp(subagent, 30)
    _stamp(main_transcript, 1)

    live = live_transcripts(fake_home, within_minutes=60)
    assert [path for path, _ in live] == [main_transcript, subagent]

    _stamp(subagent, 0)
    assert live_transcripts(fake_home, within_minutes=60)[0][0] == subagent


def test_a_session_with_no_history_behind_it_is_not_placed(conn, fake_home, main_transcript):
    """One session is not a baseline, so nothing is placed against anything.

    The counts are still shown — withholding them would be its own dishonesty —
    but no percentile is claimed.
    """
    _live_is_the_main_session(fake_home, main_transcript)

    now = look(conn, fake_home, within_minutes=60)
    assert now is not None
    assert now.placements == []
    assert any("too few to place" in note for note in now.notes)
    assert now.tool_calls > 0, "the raw numbers are still reported"


def test_a_placement_carries_what_it_was_placed_against(conn, fake_home, fake_project,
                                                       main_transcript):
    """"90th percentile" means nothing without "of ten"."""
    _live_is_the_main_session(fake_home, main_transcript)
    ingest(conn, fake_home)
    for i in range(6):
        add_session(conn, f"past{i}", project_root=str(fake_project),
                    user=10, assistant=20, minutes=60.0, tools=["Bash:git status"] * 40)

    now = look(conn, fake_home, within_minutes=60)
    assert now.placements, "six past sessions is enough to place one"
    for placement in now.placements:
        assert placement.n == 6
        assert 0 <= placement.percentile <= 100
    assert any("fact, not a judgement" in note for note in now.notes)


def test_a_placement_has_no_score_and_no_severity(conn, fake_home, fake_project,
                                                 main_transcript):
    """The screen states where a session sits. It does not grade it.

    A field called `severity` would be printed by somebody eventually, and
    "this session is going badly" is not a claim one session can support.
    """
    _live_is_the_main_session(fake_home, main_transcript)
    ingest(conn, fake_home)
    for i in range(6):
        add_session(conn, f"past{i}", project_root=str(fake_project),
                    user=10, assistant=20, minutes=60.0, tools=["Bash:git status"] * 40)

    now = look(conn, fake_home, within_minutes=60)
    fields = set(vars(now.placements[0]))
    assert not fields & {"score", "severity", "status", "verdict", "healthy", "ok"}
    assert fields >= {"metric", "value", "percentile", "median", "band", "n"}


def test_a_second_look_reads_only_what_was_appended(conn, fake_home, main_transcript):
    """A live view is looked at repeatedly, so it has to cost new bytes only."""
    _live_is_the_main_session(fake_home, main_transcript)
    look(conn, fake_home, within_minutes=60)
    with main_transcript.open("a") as fh:
        fh.write(json.dumps(_record(6)) + "\n")

    now = look(conn, fake_home, within_minutes=60)
    assert 0 < now.bytes_read < 400, "the appended record, not the file"


def test_ingest_keeps_up_with_a_live_writer(conn, fake_home, main_transcript):
    """The one that has been owed since milestone 1.

    A real writer appending in fragments, a reader catching up while it does.
    Every record must arrive exactly once, and a half-written record must never
    be consumed — reading it early loses it when the rest arrives.
    """
    total = 40
    done = threading.Event()

    def writer():
        with main_transcript.open("a", buffering=1) as fh:
            for n in range(10, 10 + total):
                line = json.dumps(_record(n)) + "\n"
                # Split each record so the file spends real time ending
                # mid-line, which is what a transcript being written looks like.
                fh.write(line[:len(line) // 2])
                fh.flush()
                time.sleep(0.001)
                fh.write(line[len(line) // 2:])
                fh.flush()
        done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    deadline = time.monotonic() + 20
    try:
        while not done.is_set() and time.monotonic() < deadline:
            ingest_one(conn, main_transcript, fake_home)
            time.sleep(0.005)
    finally:
        thread.join(timeout=20)
    ingest_one(conn, main_transcript, fake_home)   # the final catch-up

    landed = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE uuid LIKE 'live%'").fetchone()["n"]
    assert landed == total, "every record exactly once, none lost to a partial read"

    offset = conn.execute("SELECT last_offset FROM files WHERE path = ?",
                          (str(main_transcript),)).fetchone()["last_offset"]
    assert offset == main_transcript.stat().st_size, "caught up to the end"


def test_a_half_written_record_is_never_consumed(conn, fake_home, main_transcript):
    """The failure this guards is silent: consume half a line and the record is
    gone for good when the rest arrives."""
    line = json.dumps(_record(7)) + "\n"
    with main_transcript.open("a") as fh:
        fh.write(line[:30])

    ingest_one(conn, main_transcript, fake_home)
    assert conn.execute("SELECT COUNT(*) n FROM messages WHERE uuid = 'live7'"
                        ).fetchone()["n"] == 0

    with main_transcript.open("a") as fh:
        fh.write(line[30:])

    ingest_one(conn, main_transcript, fake_home)
    assert conn.execute("SELECT COUNT(*) n FROM messages WHERE uuid = 'live7'"
                        ).fetchone()["n"] == 1


@pytest.mark.parametrize("value,others,expected", [
    (10.0, [1.0, 2.0, 3.0], 100),
    (0.0, [1.0, 2.0, 3.0], 0),
    (2.5, [1.0, 2.0, 3.0, 4.0], 50),
])
def test_the_percentile_is_the_plain_count(value, others, expected):
    """Percentage of past sessions strictly below. No interpolation: with ten
    sessions on record, the only honest reading is "higher than nine of ten"."""
    from atlas.now import _percentile
    assert _percentile(value, others) == expected
