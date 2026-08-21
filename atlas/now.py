"""What is happening in the session being written right now.

⚠️ **A live session is n = 1.** Everything else in this codebase compares groups
of sessions and refuses when the groups are too small; this screen looks at a
single one, so it can only ever state facts and place them. "This session has
made 412 tool calls, more than 9 of the 10 sessions this project has on record"
is a fact. "This session is going badly" is a judgement those numbers cannot
support, and nothing here is allowed to imply it.

That constraint decides the whole design:

- Every number is shown with what it is being compared against, and with how
  many sessions that comparison rests on.
- Where the project has no baseline — fewer than five sessions — nothing is
  placed at all. The raw numbers are still shown.
- There is no score, no traffic light, and no advice. A percentile is not a
  verdict, and a screen that colours one red teaches the reader otherwise.

Nothing here is stored. A live view is the one thing in this project that is
genuinely ephemeral: the underlying rows are already in the database, put there
by the same incremental ingest, and a snapshot of "how it looked at 14:02" would
be a second copy of a number nobody can act on later.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .baseline import build
from .ingest import ingest_one
from .paths import classify, claude_home, transcript_files

# How recently a transcript must have been written to count as live. Generous on
# purpose: a session where somebody is reading rather than typing goes quiet for
# minutes at a time, and calling that "over" would be wrong far more often than
# calling a finished session "live" is annoying.
LIVE_WINDOW_MINUTES = 20

# Recent tool calls to show — what it is doing, not what it did.
RECENT_CALLS = 8


@dataclass(frozen=True)
class Placement:
    """One metric, its value now, and where that sits among past sessions."""

    metric: str
    value: float
    percentile: int | None
    median: float | None
    band: tuple[float, float] | None
    n: int

    @property
    def outside_band(self) -> bool:
        return bool(self.band) and not (self.band[0] <= self.value <= self.band[1])


@dataclass
class Now:
    path: Path
    session_id: str | None = None
    project_root: str | None = None
    kind: str = "main"
    started: str | None = None
    last_write: datetime | None = None
    bytes_read: int = 0
    user_turns: int = 0
    assistant_turns: int = 0
    tool_calls: int = 0
    recent: list[str] = field(default_factory=list)
    placements: list[Placement] = field(default_factory=list)
    baseline_n: int = 0
    baseline_confidence: str = "unknown"
    notes: list[str] = field(default_factory=list)

    @property
    def idle_minutes(self) -> float | None:
        if self.last_write is None:
            return None
        return (datetime.now(UTC) - self.last_write).total_seconds() / 60


def live_transcripts(root: Path | None = None, within_minutes: int = LIVE_WINDOW_MINUTES,
                     project_dir: str | None = None) -> list[tuple[Path, datetime]]:
    """Transcripts written to recently, newest first.

    The filesystem answers this, not the database: a session that started ten
    seconds ago has no rows yet. See decisions/0003.
    """
    cutoff = datetime.now(UTC).timestamp() - within_minutes * 60
    found = []
    for path in transcript_files(root):
        # Substring, not an exact part: the directory is the whole encoded path
        # (`-home-sean-dev-budget-buddy`), and nobody types that.
        if project_dir and not any(project_dir in part for part in path.parts):
            continue
        stat = path.stat()
        if stat.st_mtime >= cutoff:
            found.append((path, datetime.fromtimestamp(stat.st_mtime, UTC)))
    return sorted(found, key=lambda pair: pair[1], reverse=True)


def _percentile(value: float, others: list[float]) -> int | None:
    """Percentage of past sessions strictly below this one.

    Deliberately plain: no interpolation, no smoothing. With ten sessions on
    record the only honest reading of "90th percentile" is "higher than nine of
    the ten", and the count is printed next to it so it reads that way.
    """
    if not others:
        return None
    return round(100 * sum(1 for other in others if other < value) / len(others))


def look(conn, root: Path | None = None, project_dir: str | None = None,
         within_minutes: int = LIVE_WINDOW_MINUTES) -> Now | None:
    root = root or claude_home()
    live = live_transcripts(root, within_minutes, project_dir)
    if not live:
        return None
    path, last_write = live[0]

    # Catch up on this file alone — new bytes only. A live transcript ends
    # mid-line, and ingest stops before the partial one, so reading it while it
    # is being appended to is safe at any moment.
    result = ingest_one(conn, path, root)

    project, kind, _ = classify(path, root)
    row = conn.execute("SELECT * FROM sessions WHERE source_path = ?", (str(path),)).fetchone()
    now = Now(path=path, last_write=last_write, bytes_read=result.bytes_read, kind=kind)
    if row is None:
        now.notes.append(f"{project}: transcript has no parsed records yet")
        return now

    now.session_id = row["id"]
    now.project_root = row["project_root"]
    now.started = row["started"]
    counts = conn.execute("""
        SELECT (SELECT COUNT(*) FROM messages WHERE session_id = ? AND type = 'user')      u,
               (SELECT COUNT(*) FROM messages WHERE session_id = ? AND type = 'assistant') a,
               (SELECT COUNT(*) FROM tool_calls WHERE session_id = ?)                      t
    """, (row["id"], row["id"], row["id"])).fetchone()
    now.user_turns, now.assistant_turns, now.tool_calls = counts["u"], counts["a"], counts["t"]
    now.recent = [r["sig"] for r in conn.execute("""
        SELECT COALESCE(t.signature, t.name) AS sig
          FROM tool_calls t JOIN messages m ON m.uuid = t.message_uuid
         WHERE t.session_id = ? ORDER BY m.byte_offset DESC, t.seq DESC LIMIT ?
    """, (row["id"], RECENT_CALLS))][::-1]

    if now.assistant_turns == 0:
        now.notes.append("no assistant turn yet — nothing to compare")
        return now

    # The comparison is milestone 4's, reused: same eligibility, same metrics,
    # same definitions. A live session measured differently from the sessions it
    # is being placed among would not be a placement.
    base = build(conn, now.project_root, kind=kind)
    now.baseline_n, now.baseline_confidence = base.n, base.confidence
    mine = base.values.get(row["id"], {})

    if not base.states_a_norm:
        now.notes.append(
            f"{base.n} past session(s) — too few to place this one against "
            "(the numbers above are still numbers)")
        return now

    for metric, value in sorted(mine.items()):
        others = [values[metric] for session, values in base.values.items()
                  if session != row["id"] and metric in values]
        if not others:
            continue
        summary = base.summary(metric)
        now.placements.append(Placement(
            metric, value, _percentile(value, others),
            summary.median if summary else None,
            (summary.low, summary.high) if summary else None, len(others)))

    now.notes.append(
        f"placed against {len(base.counted) - 1} earlier session(s) in this project, "
        f"confidence {base.confidence} — a placement is a fact, not a judgement")
    return now
