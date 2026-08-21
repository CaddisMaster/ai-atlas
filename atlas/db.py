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
    _add_missing_columns(conn)
    return conn


# Below 1.0 the schema rebuilds rather than migrates (VERSIONING.md), but a
# column added to an existing table is one statement and the alternative is an
# existing database failing with "no such column". Additive only — anything
# that needs data moved is a rebuild.
ADDED_COLUMNS = [("sessions", "project_root", "TEXT")]


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, column, decl in ADDED_COLUMNS:
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def note_record_type(conn: sqlite3.Connection, rtype: str, known: bool, ts: str | None) -> None:
    conn.execute(
        """
        INSERT INTO record_types (type, parser_version, known, count, first_seen)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(type, parser_version) DO UPDATE SET count = count + 1
        """,
        (rtype, PARSER_VERSION, int(known), ts),
    )
