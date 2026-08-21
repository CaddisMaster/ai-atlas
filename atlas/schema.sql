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
    project_root       TEXT,       -- working directory the session ran in, from `cwd`
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

-- Configuration, resolved across every scope and stored as a snapshot rather
-- than a current value. "Did that change help?" needs a before as well as an
-- after, so config is history, not state. See docs/decisions/0001.

CREATE TABLE IF NOT EXISTS config_snap (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    taken           TEXT NOT NULL,
    project_root    TEXT,          -- absolute path; NULL = machine-wide scopes only
    project_dir     TEXT,          -- matching name under ~/.claude/projects, when known
    fingerprint     TEXT NOT NULL, -- of the whole resolution, so an unchanged re-run is not a new snapshot
    parser_version  INTEGER NOT NULL
);

-- Every place we looked, found or not. This table is the evidence for the
-- expensive claim "you have never configured X" — without it, absence of a row
-- in config_items is indistinguishable from never having checked.
CREATE TABLE IF NOT EXISTS config_scopes (
    snap_id  INTEGER NOT NULL REFERENCES config_snap(id),
    scope    TEXT NOT NULL,
    path     TEXT NOT NULL,
    state    TEXT NOT NULL CHECK (state IN ('present', 'absent', 'unknown')),
    detail   TEXT,
    PRIMARY KEY (snap_id, scope, path)
);

CREATE TABLE IF NOT EXISTS config_items (
    snap_id         INTEGER NOT NULL REFERENCES config_snap(id),
    kind            TEXT NOT NULL,   -- agent | command | skill | hook | setting | memory | mcp
    name            TEXT NOT NULL,
    scope           TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    detail          TEXT,            -- short preview only; see config.PREVIEW_CHARS
    value_hash      TEXT,            -- full value's hash, so a change is detectable
    shadowed        INTEGER NOT NULL DEFAULT 0,
    parser_version  INTEGER NOT NULL,
    PRIMARY KEY (snap_id, kind, name, scope, source_path)
);
CREATE INDEX IF NOT EXISTS idx_config_items_kind ON config_items(kind, name);

-- Permission rules get their own table because they are the thing later
-- milestones match tool calls against: "this deny rule has been hit six times".
CREATE TABLE IF NOT EXISTS rules (
    snap_id         INTEGER NOT NULL REFERENCES config_snap(id),
    scope           TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('allow', 'deny', 'ask')),
    tool            TEXT NOT NULL,
    argument        TEXT,
    pattern         TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    parser_version  INTEGER NOT NULL,
    PRIMARY KEY (snap_id, scope, action, pattern, source_path)
);
CREATE INDEX IF NOT EXISTS idx_rules_tool ON rules(tool);

-- Handoff runs: what the status document claimed, and what the repository said.
-- Kept as history so "this has been wrong since Tuesday" is answerable.

CREATE TABLE IF NOT EXISTS handoff_snap (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    taken           TEXT NOT NULL,
    repo            TEXT NOT NULL,
    head            TEXT,
    status_path     TEXT,
    fingerprint     TEXT NOT NULL,
    parser_version  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS handoff_findings (
    snap_id     INTEGER NOT NULL REFERENCES handoff_snap(id),
    check_name  TEXT NOT NULL,
    subject     TEXT NOT NULL,
    claim       TEXT,
    actual      TEXT,
    state       TEXT NOT NULL CHECK (state IN ('stale', 'ok', 'unknown')),
    source      TEXT,
    PRIMARY KEY (snap_id, check_name, subject, source)
);
