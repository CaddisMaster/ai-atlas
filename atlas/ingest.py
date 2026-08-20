"""Incremental transcript ingest.

The filesystem is the source of truth and nothing pushes to us
(docs/decisions/0003). Transcripts are JSONL and append-only, so a watermark of
``(inode, size, last_offset, prefix_hash)`` per file makes re-ingest cost
proportional to *new bytes only* — a 49 MB transcript that grew by 40 KB costs
40 KB to catch up on.

Three things invalidate a watermark and force a full re-read: the file shrank,
the inode changed, or the first bytes changed. Those cover rotation, compaction
and replacement.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import PARSER_VERSION
from .db import note_record_type
from .paths import classify, transcript_files

PREFIX_BYTES = 4096

# Record types we model. Anything outside this set still gets counted in
# record_types with known=0, so format drift shows up as a number rather than as
# missing data.
MODELLED = {"user", "assistant"}
KNOWN_UNMODELLED = {
    "system", "attachment", "mode", "permission-mode", "ai-title", "last-prompt",
    "queue-operation", "file-history-snapshot", "file-history-delta", "summary",
}


@dataclass
class Result:
    files_seen: int = 0
    files_read: int = 0
    bytes_read: int = 0
    sessions: int = 0
    messages: int = 0
    tool_calls: int = 0
    unknown_types: set[str] = field(default_factory=set)


def _prefix_hash(path: Path, length: int) -> str:
    """Hash the first ``length`` bytes.

    ⚠️ The length must be capped at bytes we have *already consumed*, never at a
    fixed window. A transcript under PREFIX_BYTES would otherwise have its whole
    body hashed, so every append would change the hash and invalidate its own
    watermark — turning incremental ingest back into a full re-read for exactly
    the small, actively-growing files that matter most. Caught by
    test_appended_lines_cost_only_the_new_bytes.
    """
    if length <= 0:
        return ""
    with path.open("rb") as fh:
        return hashlib.sha256(fh.read(length)).hexdigest()


def _hash_len(offset: int) -> int:
    return min(PREFIX_BYTES, offset)


def _watermark(conn, path: Path) -> int:
    """Byte offset to resume from — 0 when the file must be re-read in full."""
    st = path.stat()
    row = conn.execute("SELECT * FROM files WHERE path = ?", (str(path),)).fetchone()
    if row is None:
        return 0
    if row["parser_version"] != PARSER_VERSION:
        return 0            # our reading of the format changed
    if st.st_size < row["last_offset"]:
        return 0            # truncated or rotated
    if row["inode"] != st.st_ino:
        return 0            # replaced
    if row["prefix_hash"] != _prefix_hash(path, _hash_len(row["last_offset"])):
        return 0            # rewritten in place
    return row["last_offset"]


def session_id_for(path: Path, kind: str, record_session_id: str | None) -> str:
    """Identity for the session a transcript belongs to.

    ⚠️ For subagents the ``sessionId`` field is **the parent's**, not the
    subagent's — all four subagent transcripts on the machine this was written
    against carry their parent session's id. Keying on that field therefore
    merges a subagent into its parent and, depending on read order, relabels the
    parent as a subagent. The file path is the only reliable identity here.
    """
    if kind == "subagent":
        return path.stem              # agent-<id>
    return record_session_id or path.stem


def _upsert_session(conn, project: str, kind: str, parent: str | None,
                    path: Path, session_id: str) -> None:
    conn.execute(
        """
        INSERT INTO sessions (id, project, kind, parent_session_id, source_path, parser_version)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (session_id, project, kind, parent, str(path), PARSER_VERSION),
    )


def _ingest_file(conn, path: Path, root: Path | None, res: Result) -> None:
    offset = _watermark(conn, path)
    st = path.stat()
    if offset >= st.st_size:
        return  # nothing new

    res.files_read += 1
    project, kind, parent = classify(path, root)
    seen_session: str | None = None

    with path.open("rb") as fh:
        fh.seek(offset)
        while True:
            line_start = fh.tell()
            raw = fh.readline()
            if not raw:
                break
            # A trailing partial line means the session is still being written.
            # Stop here and leave the watermark before it; next run picks it up.
            if not raw.endswith(b"\n"):
                offset = line_start
                break
            offset = fh.tell()
            res.bytes_read += len(raw)

            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                note_record_type(conn, "!malformed", False, None)
                res.unknown_types.add("!malformed")
                continue
            if not isinstance(rec, dict):
                continue

            rtype = rec.get("type") or "!untyped"
            ts = rec.get("timestamp")
            known = rtype in MODELLED or rtype in KNOWN_UNMODELLED
            note_record_type(conn, rtype, known, ts)
            if not known:
                res.unknown_types.add(rtype)

            session_id = session_id_for(path, kind, rec.get("sessionId"))
            if session_id != seen_session:
                _upsert_session(conn, project, kind, parent, path, session_id)
                seen_session = session_id

            if rtype not in MODELLED:
                continue

            uuid = rec.get("uuid")
            if not uuid:
                continue

            msg = rec.get("message") or {}
            conn.execute(
                """
                INSERT INTO messages (uuid, session_id, parent_uuid, type, role, ts,
                                      byte_offset, parser_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO NOTHING
                """,
                (uuid, session_id, rec.get("parentUuid"), rtype, msg.get("role"),
                 ts, line_start, PARSER_VERSION),
            )
            res.messages += 1

            usage = msg.get("usage") or {}
            if usage:
                conn.execute(
                    """
                    INSERT INTO usage (message_uuid, input, output, cache_read, cache_creation)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(message_uuid) DO NOTHING
                    """,
                    (uuid, usage.get("input_tokens"), usage.get("output_tokens"),
                     usage.get("cache_read_input_tokens"), usage.get("cache_creation_input_tokens")),
                )

            content = msg.get("content")
            if isinstance(content, list):
                for seq, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        conn.execute(
                            """
                            INSERT INTO tool_calls (message_uuid, seq, session_id, name)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(message_uuid, seq) DO NOTHING
                            """,
                            (uuid, seq, session_id, block.get("name") or "?"),
                        )
                        res.tool_calls += 1

    conn.execute(
        """
        INSERT INTO files (path, inode, size, last_offset, prefix_hash, parser_version, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            inode = excluded.inode, size = excluded.size,
            last_offset = excluded.last_offset, prefix_hash = excluded.prefix_hash,
            parser_version = excluded.parser_version, last_seen = excluded.last_seen
        """,
        (str(path), st.st_ino, st.st_size, offset, _prefix_hash(path, _hash_len(offset)),
         PARSER_VERSION, datetime.now(UTC).isoformat()),
    )


def ingest(conn, root: Path | None = None) -> Result:
    res = Result()
    for path in transcript_files(root):
        res.files_seen += 1
        _ingest_file(conn, path, root, res)

    # Session boundaries are derived, not recorded: the transcript has no
    # "session ended" marker, so first and last message timestamps are it.
    conn.execute(
        """
        UPDATE sessions SET
            started = (SELECT MIN(ts) FROM messages WHERE messages.session_id = sessions.id),
            ended   = (SELECT MAX(ts) FROM messages WHERE messages.session_id = sessions.id)
        """
    )
    res.sessions = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
    conn.commit()
    return res
