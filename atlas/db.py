"""SQLite access. One file, no server — see docs/decisions/0002."""

import os
import sqlite3
from pathlib import Path

from . import PARSER_VERSION

SCHEMA = Path(__file__).with_name("schema.sql")


def default_path() -> Path:
    return Path(os.environ.get("ATLAS_DB", Path.home() / ".local" / "share" / "ai-atlas" / "atlas.db"))


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path) if path else default_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA.read_text())
    return conn


def note_record_type(conn: sqlite3.Connection, rtype: str, known: bool, ts: str | None) -> None:
    conn.execute(
        """
        INSERT INTO record_types (type, parser_version, known, count, first_seen)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(type, parser_version) DO UPDATE SET count = count + 1
        """,
        (rtype, PARSER_VERSION, int(known), ts),
    )
