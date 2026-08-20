import json
from pathlib import Path

import pytest

from atlas.db import connect


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


@pytest.fixture
def fake_home(tmp_path):
    """A ~/.claude with one main session and one subagent transcript beneath it.

    The subagent path is the point: it sits one level deeper than a main
    session, and a two-level glob misses it entirely.
    """
    root = tmp_path / ".claude"
    proj = root / "projects" / "-home-sean-demo"

    _write(proj / "aaaa1111.jsonl", [
        {"type": "user", "uuid": "u1", "sessionId": "aaaa1111", "timestamp": "2026-08-20T10:00:00Z",
         "message": {"role": "user", "content": "go"}},
        {"type": "assistant", "uuid": "a1", "parentUuid": "u1", "sessionId": "aaaa1111",
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
        {"type": "assistant", "uuid": "s1", "sessionId": "aaaa1111",
         "timestamp": "2026-08-20T10:01:00Z",
         "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Grep"}]}},
    ])
    return root
