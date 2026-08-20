-- ai-atlas storage. SQLite, deliberately: see docs/decisions/0002.
--
-- Every table that holds parsed data carries `parser_version`, so a change in
-- the transcript format leaves a visible seam instead of a silent one.

CREATE TABLE IF NOT EXISTS files (
    path            TEXT PRIMARY KEY,
    inode           INTEGER,
    size            INTEGER NOT NULL,
    last_offset     INTEGER NOT NULL DEFAULT 0,
    prefix_hash     TEXT,
    parser_version  INTEGER NOT NULL,
    last_seen       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                 TEXT PRIMARY KEY,
    project            TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('main', 'subagent')),
    parent_session_id  TEXT,
    source_path        TEXT NOT NULL,
    started            TEXT,
    ended              TEXT,
    parser_version     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    uuid            TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    parent_uuid     TEXT,
    type            TEXT NOT NULL,
    role            TEXT,
    ts              TEXT,
    byte_offset     INTEGER NOT NULL,
    parser_version  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_ts      ON messages(ts);

CREATE TABLE IF NOT EXISTS tool_calls (
    message_uuid  TEXT NOT NULL REFERENCES messages(uuid),
    seq           INTEGER NOT NULL,
    session_id    TEXT NOT NULL,
    name          TEXT NOT NULL,
    PRIMARY KEY (message_uuid, seq)
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(name);

CREATE TABLE IF NOT EXISTS usage (
    message_uuid    TEXT PRIMARY KEY REFERENCES messages(uuid),
    input           INTEGER,
    output          INTEGER,
    cache_read      INTEGER,
    cache_creation  INTEGER
);

-- Every record type seen, modelled or not. Nothing is invisible.
CREATE TABLE IF NOT EXISTS record_types (
    type            TEXT NOT NULL,
    parser_version  INTEGER NOT NULL,
    known           INTEGER NOT NULL,
    count           INTEGER NOT NULL DEFAULT 0,
    first_seen      TEXT,
    PRIMARY KEY (type, parser_version)
);
