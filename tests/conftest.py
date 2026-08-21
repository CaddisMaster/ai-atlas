import json
from pathlib import Path

import pytest

from atlas.db import connect
from atlas.paths import encode_project_dir


@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def _write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


@pytest.fixture
def fake_project(tmp_path):
    """A project directory configured the way a real one is.

    Everything here mirrors something on the machine this was written against:
    a permissions block, a `Stop` hook pointing at a script through
    `$CLAUDE_PROJECT_DIR`, subagents as loose `.md` files, a slash command, a
    skill as a *directory* holding `SKILL.md`, and both memory files.
    """
    root = tmp_path / "work" / "demo-app"
    claude = root / ".claude"

    _text(claude / "settings.json", json.dumps({
        "permissions": {
            "allow": ["Bash(./test.sh)", "Bash(git status*)", "Read(~/notes/**)"],
            "deny": ["Bash(git push --force*)"],
        },
        "hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/changelog-guard.sh"},
        ]}]},
    }))
    _text(claude / "hooks" / "changelog-guard.sh", "#!/usr/bin/env bash\nexit 0\n")
    for agent in ("test-first", "sweeper"):
        _text(claude / "agents" / f"{agent}.md", f"---\nname: {agent}\n---\n")
    _text(claude / "commands" / "wrap.md", "Wrap the session up.\n")
    _text(claude / "skills" / "verify" / "SKILL.md", "---\nname: verify\n---\n")
    _text(root / "CLAUDE.md", "# demo-app\n\nProject instructions.\n")
    _text(root / "CLAUDE.local.md", "Droplet access notes.\n")
    return root


@pytest.fixture
def fake_home(tmp_path, fake_project):
    """A ~/.claude with one main session and one subagent transcript beneath it.

    Two details are faithful rather than convenient, and both are load-bearing:
    the subagent sits one level deeper than the main session, and its record
    carries the **parent's** `sessionId`. Records also carry `cwd`, including
    one from a subdirectory, because that is how the project root is recovered.
    """
    root = tmp_path / ".claude"
    proj = root / "projects" / encode_project_dir(fake_project)
    cwd = str(fake_project)

    _write(proj / "aaaa1111.jsonl", [
        {"type": "user", "uuid": "u1", "sessionId": "aaaa1111", "cwd": cwd,
         "timestamp": "2026-08-20T10:00:00Z",
         "message": {"role": "user", "content": "go"}},
        {"type": "assistant", "uuid": "a1", "parentUuid": "u1", "sessionId": "aaaa1111",
         "cwd": str(fake_project / "app" / "templates"),   # a session can wander
         "timestamp": "2026-08-20T10:00:05Z",
         "message": {"role": "assistant",
                     "usage": {"input_tokens": 3, "output_tokens": 20,
                               "cache_read_input_tokens": 900, "cache_creation_input_tokens": 100},
                     "content": [{"type": "tool_use", "name": "Bash"},
                                 {"type": "tool_use", "name": "Read"}]}},
        {"type": "mode", "mode": "auto"},
        {"type": "brand-new-record-type-from-the-future", "timestamp": "2026-08-20T10:00:06Z"},
    ])

    _write(proj / "aaaa1111" / "subagents" / "agent-b222.jsonl", [
        # ⚠️ faithful to real data: a subagent record carries the PARENT session id
        {"type": "assistant", "uuid": "s1", "sessionId": "aaaa1111", "cwd": cwd,
         "timestamp": "2026-08-20T10:01:00Z",
         "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Grep"}]}},
    ])

    # ~/.claude.json is a sibling *file*, not part of the directory. It holds the
    # "always allow" answers, which appear in no settings.json anywhere.
    _text(tmp_path / ".claude.json", json.dumps({
        "projects": {str(fake_project): {
            "allowedTools": ["Bash(npm test:*)"],
            "hasTrustDialogAccepted": True,
        }},
    }))

    _text(root / "settings.json", json.dumps({
        "model": "opus",
        "permissions": {"deny": ["Read(./.env)"]},
    }))
    return root


@pytest.fixture
def main_transcript(fake_home, fake_project):
    return fake_home / "projects" / encode_project_dir(fake_project) / "aaaa1111.jsonl"


def add_session(conn, session_id, *, project_root="/work/demo-app", kind="main",
                user=2, assistant=3, tools=(), minutes=30.0,
                started="2026-08-20T10:00:00+00:00", usage=None):
    """Insert one session's rows directly.

    Baselines are computed from the database, so these fixtures build database
    rows rather than transcripts — the path from JSONL to these tables is
    covered by the ingest tests. The shapes mirror the corpus: a handful of long
    tool-heavy sessions, a couple of short ones, and sessions with no assistant
    turn at all, which really do exist.
    """
    from datetime import datetime, timedelta

    conn.execute(
        "INSERT INTO sessions (id, project, kind, source_path, project_root, parser_version)"
        " VALUES (?, ?, ?, ?, ?, 2)",
        (session_id, "-work-demo-app", kind, f"/t/{session_id}.jsonl", project_root))

    begin = datetime.fromisoformat(started)
    total = user + assistant
    step = timedelta(minutes=minutes / max(total - 1, 1))
    order = ["user"] * user + ["assistant"] * assistant
    first_assistant = None
    for i, role in enumerate(order):
        uuid = f"{session_id}-m{i}"
        conn.execute(
            "INSERT INTO messages (uuid, session_id, type, role, ts, byte_offset, parser_version)"
            " VALUES (?, ?, ?, ?, ?, ?, 2)",
            (uuid, session_id, role, role, (begin + step * i).isoformat().replace("+00:00", "Z"), i))
        if role == "assistant" and first_assistant is None:
            first_assistant = uuid

    # Session boundaries are derived, not recorded — the same UPDATE ingest runs.
    conn.execute(
        "UPDATE sessions SET"
        " started = (SELECT MIN(ts) FROM messages WHERE messages.session_id = sessions.id),"
        " ended   = (SELECT MAX(ts) FROM messages WHERE messages.session_id = sessions.id)"
        " WHERE id = ?", (session_id,))

    for seq, name in enumerate(tools):
        conn.execute(
            "INSERT INTO tool_calls (message_uuid, seq, session_id, name) VALUES (?, ?, ?, ?)",
            (first_assistant, seq, session_id, name))

    if usage and first_assistant:
        conn.execute(
            "INSERT INTO usage (message_uuid, input, output, cache_read, cache_creation)"
            " VALUES (?, ?, ?, ?, ?)",
            (first_assistant, usage.get("input", 0), usage.get("output", 0),
             usage.get("cache_read", 0), usage.get("cache_creation", 0)))
    conn.commit()
