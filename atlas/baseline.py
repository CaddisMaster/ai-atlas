"""What a normal session looks like in one project, and which ones were not.

⚠️ Every definition in this file is frozen under ``BASELINE_VERSION``. Changing
how something is counted is a versioned event, not a tweak: a median computed
one way and compared against a median computed another way is not a comparison.
That is the premise of the whole project (CLAUDE.md, non-negotiable 6), and this
is the first module where it bites.

The definitions, in full:

1. **A session counts if it has at least one assistant turn.** Three of the
   thirteen main sessions in the corpus this was written against have none: a
   prompt typed and abandoned, or a session that never got a reply. They are
   excluded *and recorded* — never silently dropped.
2. **Quantiles are ``statistics.quantiles(..., method="inclusive")``**, which
   interpolates linearly between order statistics and is defined for n as small
   as 2. Any other quantile convention gives different numbers on samples this
   size, so the convention is part of the measurement.
3. **The normal band is the Tukey fence**, ``[p25 - 1.5·IQR, p75 + 1.5·IQR]``,
   clamped at zero for quantities that cannot be negative. It assumes nothing
   about the distribution, which matters because these distributions are not
   normal and n is small.
4. **Confidence comes from n alone** — see ``CONFIDENCE``. Below the floor no
   norm is stated at all. "Unknown" is a real answer here: three of the four
   projects in the corpus do not have enough sessions to have a normal.

None of this makes a small sample bigger. It makes the smallness visible, which
is the only honest thing available.
"""

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

BASELINE_VERSION = 1

# n < 5: say nothing. 5–11: provisional. 12+: established.
# The thresholds are a judgement, not a derivation — which is exactly why they
# are frozen under BASELINE_VERSION and printed alongside every answer.
FLOOR, ESTABLISHED = 5, 12
CONFIDENCE = ("unknown", "provisional", "established")

TUKEY = 1.5

# Every metric here is non-negative, so the low fence is clamped at zero rather
# than reported as a negative session count. These ones are also *rates* and
# cannot exceed 1: a band whose upper edge is 1.01 invites the reader to wonder
# what a 101% cache hit rate would look like.
BOUNDED = ("cache_hit_rate",)
BOUNDED_PREFIX = "share_"

TOP_TOOLS = 5


@dataclass(frozen=True)
class Summary:
    metric: str
    n: int
    p25: float
    median: float
    p75: float
    low: float
    high: float

    @property
    def iqr(self) -> float:
        return self.p75 - self.p25

    @property
    def spread(self) -> float | None:
        """p75 / p25 — how wide the middle half is, in multiples.

        Printed because a band can be arithmetically correct and still say
        nothing: in the corpus this was written against, the middle half of
        `tool_calls` runs from 68 to 343, so the fence reaches 755 and no
        session on earth would fall outside it.
        """
        return self.p75 / self.p25 if self.p25 else None


@dataclass(frozen=True)
class Outlier:
    session_id: str
    metric: str
    value: float
    direction: str      # high | low
    band: tuple[float, float]


@dataclass
class Baseline:
    project_root: str | None
    kind: str
    counted: list[str] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)   # (session_id, reason)
    summaries: list[Summary] = field(default_factory=list)
    outliers: list[Outlier] = field(default_factory=list)
    values: dict[str, dict[str, float]] = field(default_factory=dict)  # session -> metric -> value

    @property
    def n(self) -> int:
        return len(self.counted)

    @property
    def confidence(self) -> str:
        if self.n < FLOOR:
            return "unknown"
        return "established" if self.n >= ESTABLISHED else "provisional"

    @property
    def states_a_norm(self) -> bool:
        return self.confidence != "unknown"

    def summary(self, metric: str) -> Summary | None:
        return next((s for s in self.summaries if s.metric == metric), None)


def _rows(conn, project_root: str | None, kind: str):
    """One row per session with the counts every metric is derived from."""
    where = ["s.kind = ?"]
    params: list[object] = [kind]
    if project_root:
        where.append("s.project_root = ?")
        params.append(project_root)
    return conn.execute(f"""
        SELECT s.id, s.started, s.ended,
               (SELECT COUNT(*) FROM messages m
                 WHERE m.session_id = s.id AND m.type = 'user')      AS user_turns,
               (SELECT COUNT(*) FROM messages m
                 WHERE m.session_id = s.id AND m.type = 'assistant') AS assistant_turns,
               (SELECT COUNT(*) FROM tool_calls t
                 WHERE t.session_id = s.id)                          AS tool_calls,
               (SELECT COALESCE(SUM(u.output), 0) FROM usage u
                  JOIN messages m ON m.uuid = u.message_uuid
                 WHERE m.session_id = s.id)                          AS output_tokens,
               (SELECT COALESCE(SUM(u.cache_read), 0) FROM usage u
                  JOIN messages m ON m.uuid = u.message_uuid
                 WHERE m.session_id = s.id)                          AS cache_read,
               (SELECT COALESCE(SUM(u.cache_creation), 0) FROM usage u
                  JOIN messages m ON m.uuid = u.message_uuid
                 WHERE m.session_id = s.id)                          AS cache_creation,
               (SELECT COALESCE(SUM(u.input), 0) FROM usage u
                  JOIN messages m ON m.uuid = u.message_uuid
                 WHERE m.session_id = s.id)                          AS fresh_input
          FROM sessions s
         WHERE {' AND '.join(where)}
         ORDER BY s.id
    """, params).fetchall()


def _gaps(conn) -> dict[str, float]:
    """Largest silence inside each session, in minutes.

    The open question in `status.md` is what "a session" means when a transcript
    is resumed. This is the measurement that would show it: a resumed session
    has an hours-long gap in the middle. Nothing in the current corpus exceeds
    24 minutes, so the question stays open — but it is now a number rather than
    a suspicion.
    """
    rows = conn.execute("""
        SELECT session_id, MAX(gap) * 1440 AS minutes FROM (
            SELECT session_id,
                   julianday(ts) - julianday(LAG(ts) OVER (
                       PARTITION BY session_id ORDER BY ts)) AS gap
              FROM messages WHERE ts IS NOT NULL)
         GROUP BY session_id
    """).fetchall()
    return {r["session_id"]: r["minutes"] for r in rows if r["minutes"] is not None}


def _tool_shares(conn, session_ids: list[str]) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Per session, the share of its tool calls that went to each top tool.

    Measured per session and then summarised, rather than pooled across the
    project: a project-wide mix is dominated by whichever session was longest,
    and the question here is what a *session* normally looks like.
    """
    if not session_ids:
        return {}, []
    marks = ",".join("?" * len(session_ids))
    top = [r["name"] for r in conn.execute(
        f"SELECT name, COUNT(*) n FROM tool_calls WHERE session_id IN ({marks})"
        " GROUP BY name ORDER BY n DESC, name LIMIT ?", [*session_ids, TOP_TOOLS])]
    per: dict[str, dict[str, float]] = {}
    for row in conn.execute(
            f"SELECT session_id, name, COUNT(*) n FROM tool_calls"
            f" WHERE session_id IN ({marks}) GROUP BY session_id, name", session_ids):
        per.setdefault(row["session_id"], {})[row["name"]] = row["n"]
    shares = {}
    for sid in session_ids:
        counts = per.get(sid, {})
        total = sum(counts.values())
        shares[sid] = {f"share_{t}": (counts.get(t, 0) / total if total else 0.0) for t in top}
    return shares, [f"share_{t}" for t in top]


def _minutes(started: str | None, ended: str | None) -> float | None:
    if not started or not ended:
        return None
    try:
        a = datetime.fromisoformat(started)
        b = datetime.fromisoformat(ended)
    except ValueError:
        return None
    return (b - a).total_seconds() / 60


def summarise(metric: str, values: list[float]) -> Summary | None:
    """Quartiles and the normal band. ``None`` below two values — nothing to say."""
    if len(values) < 2:
        return None
    p25, median, p75 = statistics.quantiles(values, n=4, method="inclusive")
    iqr = p75 - p25
    low, high = max(p25 - TUKEY * iqr, 0.0), p75 + TUKEY * iqr
    if metric in BOUNDED or metric.startswith(BOUNDED_PREFIX):
        high = min(high, 1.0)
    return Summary(metric, len(values), p25, median, p75, low, high)


def build(conn, project_root: str | None = None, kind: str = "main") -> Baseline:
    base = Baseline(project_root=project_root, kind=kind)
    rows = _rows(conn, project_root, kind)
    gaps = _gaps(conn)

    counted = []
    for row in rows:
        # ⚠️ A session with no assistant turn did not happen: a prompt typed and
        # abandoned. Three of thirteen in the corpus. Excluded and recorded.
        if row["assistant_turns"] == 0:
            base.excluded.append((row["id"], "no assistant turns"))
            continue
        counted.append(row)
    base.counted = [r["id"] for r in counted]

    shares, share_metrics = _tool_shares(conn, base.counted)
    for row in counted:
        total_in = row["fresh_input"] + row["cache_read"] + row["cache_creation"]
        values: dict[str, float] = {
            "user_turns": float(row["user_turns"]),
            "assistant_turns": float(row["assistant_turns"]),
            "tool_calls": float(row["tool_calls"]),
            "tools_per_turn": row["tool_calls"] / row["assistant_turns"],
            "output_tokens": float(row["output_tokens"]),
        }
        duration = _minutes(row["started"], row["ended"])
        if duration is not None:
            values["duration_min"] = duration
        if row["id"] in gaps:
            values["gap_max_min"] = gaps[row["id"]]
        if total_in:
            values["cache_hit_rate"] = row["cache_read"] / total_in
        values.update(shares.get(row["id"], {}))
        base.values[row["id"]] = values

    metrics = ["duration_min", "gap_max_min", "user_turns", "assistant_turns", "tool_calls",
               "tools_per_turn", "output_tokens", "cache_hit_rate", *share_metrics]
    for metric in metrics:
        # Each metric carries its own n: a session with no timestamps is missing
        # from `duration_min` and present everywhere else, and the count says so.
        present = [v[metric] for v in base.values.values() if metric in v]
        summary = summarise(metric, present)
        if summary:
            base.summaries.append(summary)

    if base.states_a_norm:
        for session_id, values in base.values.items():
            for summary in base.summaries:
                value = values.get(summary.metric)
                if value is None:
                    continue
                if value > summary.high:
                    base.outliers.append(Outlier(session_id, summary.metric, value,
                                                 "high", (summary.low, summary.high)))
                elif value < summary.low:
                    base.outliers.append(Outlier(session_id, summary.metric, value,
                                                 "low", (summary.low, summary.high)))
    return base


def fingerprint(base: Baseline) -> str:
    payload = json.dumps({
        "project": base.project_root, "kind": base.kind,
        "counted": sorted(base.counted), "excluded": sorted(base.excluded),
        "summaries": [[s.metric, s.n, s.p25, s.median, s.p75] for s in base.summaries],
        "outliers": sorted((o.session_id, o.metric, o.value) for o in base.outliers),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def save(conn, base: Baseline) -> tuple[int, bool]:
    from . import PARSER_VERSION

    fp = fingerprint(base)
    last = conn.execute(
        "SELECT id, fingerprint FROM baselines WHERE project_root IS ? AND kind = ?"
        " AND baseline_version = ? ORDER BY id DESC LIMIT 1",
        (base.project_root, base.kind, BASELINE_VERSION)).fetchone()
    if last and last["fingerprint"] == fp:
        return last["id"], False

    cur = conn.execute(
        "INSERT INTO baselines (taken, project_root, kind, n_sessions, n_excluded,"
        " confidence, fingerprint, baseline_version, parser_version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), base.project_root, base.kind, base.n,
         len(base.excluded), base.confidence, fp, BASELINE_VERSION, PARSER_VERSION))
    baseline_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO baseline_metrics (baseline_id, metric, n, p25, median, p75, low, high)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(baseline_id, s.metric, s.n, s.p25, s.median, s.p75, s.low, s.high)
         for s in base.summaries])
    conn.executemany(
        "INSERT INTO baseline_outliers (baseline_id, session_id, metric, value, direction)"
        " VALUES (?, ?, ?, ?, ?)",
        [(baseline_id, o.session_id, o.metric, o.value, o.direction) for o in base.outliers])
    conn.executemany(
        "INSERT INTO baseline_exclusions (baseline_id, session_id, reason) VALUES (?, ?, ?)",
        [(baseline_id, sid, reason) for sid, reason in base.excluded])
    # Per-session values are the durable measurement: milestone 6 compares
    # sessions before an intervention with sessions after it, and that needs the
    # numbers, not the summary they rolled up into.
    conn.executemany(
        "INSERT INTO session_metrics (session_id, metric, value, baseline_version)"
        " VALUES (?, ?, ?, ?) ON CONFLICT(session_id, metric, baseline_version)"
        " DO UPDATE SET value = excluded.value",
        [(sid, metric, value, BASELINE_VERSION)
         for sid, values in base.values.items() for metric, value in values.items()])
    conn.commit()
    return baseline_id, True
