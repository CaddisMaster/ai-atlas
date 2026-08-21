"""Work that repeats, and the artifact that would capture it.

Detection is deterministic — it counts (CLAUDE.md, non-negotiable 3). Nothing
here asks a model what a sequence "means"; it finds sequences that recur across
sessions and names the kind of artifact that fits their shape. Drafting the
artifact is the human's job, later, with the evidence in front of them.

Three rules keep this from becoming a suggestion engine:

1. **Support is counted in sessions, not occurrences.** A sequence run twenty
   times in one afternoon is one habit on one day. The same sequence in three
   different sessions is how you work.
2. **Frequency is not evidence — lift is.** The most common pairs in the corpus
   are `grep → sed` and `grep → cat`, in eight sessions each. They mean nothing:
   both tools are everywhere, so they land next to each other by arithmetic.
   Their lift — observed occurrences over what the parts' own frequencies
   predict — is 2.0 and 1.2. `git add → git push → gh pr` has a lift of 249.
   Ranking by frequency buries the rituals under the noise.
3. **It has to be able to find nothing.** A project with one session, or with no
   sequence above the floor, is told that. Proposing an artifact off a single
   occurrence is how a tool teaches somebody to ignore it.

Every threshold below is frozen under ``PATTERN_VERSION``: changing what counts
as a pattern changes every count that came before it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .signature import bash_signature

PATTERN_VERSION = 1

MIN_SUPPORT = 3           # distinct sessions a sequence must appear in
MIN_LENGTH, MAX_LENGTH = 2, 5

# Occurrences over what independent frequencies predict. Below 3 the sequence is
# explained by its parts being common; the noisy pairs in this corpus sit at 1.
MIN_LIFT = 3.0

# A single call has to be much more common than a sequence before it is worth
# a permission rule: rules are cheap to add and annoying to get wrong.
PERMISSION_MIN_CALLS = 10
PERMISSION_MIN_SESSIONS = 2

# A sequence that keeps landing at the end of a session is a wrap-up ritual,
# which is a hook rather than a command somebody has to remember to type.
HOOK_TAIL = 3
HOOK_SHARE = 0.8


@dataclass(frozen=True)
class Occurrence:
    session_id: str
    message_uuid: str      # so the claim can be checked by hand in the transcript
    position: int
    from_end: int


@dataclass
class Pattern:
    sequence: tuple[str, ...]
    occurrences: list[Occurrence] = field(default_factory=list)
    lift: float = 0.0
    proposal: str = ""
    why: str = ""

    @property
    def support(self) -> int:
        return len({o.session_id for o in self.occurrences})

    @property
    def count(self) -> int:
        return len(self.occurrences)

    @property
    def text(self) -> str:
        return " → ".join(self.sequence)


@dataclass
class Proposal:
    """A single call that is used constantly and permitted by nothing."""

    signature: str
    calls: int
    sessions: int
    rule: str


@dataclass
class Report:
    project_root: str | None
    kind: str
    n_sessions: int = 0
    n_calls: int = 0
    patterns: list[Pattern] = field(default_factory=list)
    permissions: list[Proposal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def sequences(conn, project_root: str | None, kind: str) -> dict[str, list[tuple[str, str]]]:
    """Per session, its tool calls in order, as ``(signature, message_uuid)``.

    Ordered by byte offset then block index: the transcript is append-only, so
    its own order is the order things happened. Timestamps would tie within a
    single assistant message that made three calls.
    """
    where = ["s.kind = ?"]
    params: list[object] = [kind]
    if project_root:
        where.append("s.project_root = ?")
        params.append(project_root)
    rows = conn.execute(f"""
        SELECT t.session_id, COALESCE(t.signature, t.name) AS sig, t.message_uuid
          FROM tool_calls t
          JOIN messages m ON m.uuid = t.message_uuid
          JOIN sessions s ON s.id = t.session_id
         WHERE {' AND '.join(where)}
         ORDER BY t.session_id, m.byte_offset, t.seq
    """, params).fetchall()
    out: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        out.setdefault(row["session_id"], []).append((row["sig"], row["message_uuid"]))
    return out


def collapse(per_session: dict[str, list[tuple[str, str]]]) -> dict[str, list[tuple[str, str]]]:
    """Squash consecutive repeats: `grep grep cat cat cat` → `grep cat`.

    How many times in a row you grepped varies with the file. The *shape* —
    grep, then read, then edit — is the thing that repeats between sessions.
    Without this, the highest-lift patterns are all runs of one tool with a
    single interruption, which nobody can act on.

    It also removes uniform windows entirely: after collapsing, adjacent calls
    always differ, so `grep → grep → grep` cannot be reported as a sequence. It
    is a repetition, and repetitions are answered by a permission rule rather
    than a slash command.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for session_id, calls in per_session.items():
        squashed: list[tuple[str, str]] = []
        for signature, message_uuid in calls:
            if not squashed or squashed[-1][0] != signature:
                squashed.append((signature, message_uuid))
        out[session_id] = squashed
    return out


def _mine(per_session: dict[str, list[tuple[str, str]]]) -> list[Pattern]:
    found: dict[tuple[str, ...], Pattern] = {}
    for session_id, calls in per_session.items():
        signatures = [c[0] for c in calls]
        total = len(signatures)
        for length in range(MIN_LENGTH, MAX_LENGTH + 1):
            for i in range(total - length + 1):
                window = tuple(signatures[i:i + length])
                pattern = found.setdefault(window, Pattern(window))
                pattern.occurrences.append(
                    Occurrence(session_id, calls[i][1], i, total - (i + length)))
    return [p for p in found.values() if p.support >= MIN_SUPPORT]


def score(patterns: list[Pattern], per_session: dict[str, list[tuple[str, str]]]) -> list[Pattern]:
    """Attach lift, and drop everything a coincidence explains.

    lift = occurrences ÷ (n · Πp(signature)) — how many times more often the
    sequence happened than it would if each call were drawn independently.
    """
    total = sum(len(calls) for calls in per_session.values())
    frequency: dict[str, int] = {}
    for calls in per_session.values():
        for signature, _ in calls:
            frequency[signature] = frequency.get(signature, 0) + 1

    kept = []
    for pattern in patterns:
        expected = float(total)
        for signature in pattern.sequence:
            expected *= frequency.get(signature, 0) / total
        if not expected:
            continue
        pattern.lift = pattern.count / expected
        if pattern.lift >= MIN_LIFT:
            kept.append(pattern)
    return kept


def _drop_subsumed(patterns: list[Pattern]) -> list[Pattern]:
    """Keep the longest sequence when a shorter one never occurs outside it.

    `git add → git commit` and `git add → git commit → git push` with identical
    counts are one habit reported twice.
    """
    by_length = sorted(patterns, key=lambda p: (-len(p.sequence), p.text))
    kept: list[Pattern] = []
    for pattern in by_length:
        subsumed = any(
            len(longer.sequence) > len(pattern.sequence)
            and longer.count == pattern.count
            and any(longer.sequence[i:i + len(pattern.sequence)] == pattern.sequence
                    for i in range(len(longer.sequence) - len(pattern.sequence) + 1))
            for longer in kept)
        if not subsumed:
            kept.append(pattern)
    return kept


def _propose(pattern: Pattern) -> tuple[str, str]:
    tail = sum(1 for o in pattern.occurrences if o.from_end < HOOK_TAIL)
    if tail / pattern.count >= HOOK_SHARE:
        return "hook", (f"{tail} of {pattern.count} occurrences are in the last "
                        f"{HOOK_TAIL} tool calls of their session — a wrap-up ritual")
    return "slash command", (f"the same {len(pattern.sequence)} steps in "
                             f"{pattern.support} different sessions, "
                             f"{pattern.lift:.0f}× more often than chance")


def _allow_rules(conn, project_root: str | None) -> list[tuple[str, str | None]] | None:
    """Allow rules from the most recent config snapshot. ``None`` if there is none.

    ⚠️ Without the resolved rules we cannot say a call is unpermitted, so we do
    not say it. "No rule covers this" is a claim about every scope, and
    milestone 2 exists because that claim is easy to get wrong.
    """
    snap = conn.execute(
        "SELECT id FROM config_snap WHERE project_root IS ? ORDER BY id DESC LIMIT 1",
        (project_root,)).fetchone()
    if snap is None:
        return None
    return [(r["tool"], r["argument"]) for r in conn.execute(
        "SELECT tool, argument FROM rules WHERE snap_id = ? AND action = 'allow'",
        (snap["id"],))]


def _covered(signature: str, rules: list[tuple[str, str | None]]) -> bool:
    """Is this call already permitted by some allow rule?

    Deliberately generous: a rule that might cover the call counts as covering
    it. The failure we can afford is staying quiet about a permission you could
    add; the one we cannot is proposing a rule you already have.
    """
    tool, _, argument = signature.partition(":")
    for rule_tool, rule_argument in rules:
        if rule_tool != tool:
            continue
        if not rule_argument or not argument:
            return True
        literal = rule_argument.split("*")[0].split(":")[0].strip()
        if not literal or argument.startswith(literal) or literal.startswith(argument):
            return True
        if argument.startswith(bash_signature(literal)):
            return True
    return False


def _permissions(conn, per_session, project_root) -> tuple[list[Proposal], list[str]]:
    counts: dict[str, tuple[int, set[str]]] = {}
    for session_id, calls in per_session.items():
        for signature, _ in calls:
            calls_seen, sessions = counts.get(signature, (0, set()))
            counts[signature] = (calls_seen + 1, sessions | {session_id})

    rules = _allow_rules(conn, project_root)
    if rules is None:
        return [], ["permission proposals need resolved rules — run `atlas config` first"]

    proposals = []
    for signature, (calls_seen, sessions) in sorted(counts.items()):
        if calls_seen < PERMISSION_MIN_CALLS or len(sessions) < PERMISSION_MIN_SESSIONS:
            continue
        if _covered(signature, rules):
            continue
        tool, _, argument = signature.partition(":")
        proposals.append(Proposal(signature, calls_seen, len(sessions),
                                  f"{tool}({argument}:*)" if argument else tool))
    return sorted(proposals, key=lambda p: -p.calls), []


def find(conn, project_root: str | None = None, kind: str = "main") -> Report:
    raw = sequences(conn, project_root, kind)
    report = Report(project_root=project_root, kind=kind, n_sessions=len(raw),
                    n_calls=sum(len(c) for c in raw.values()))

    squashed = collapse(raw)
    patterns = _drop_subsumed(score(_mine(squashed), squashed))
    for pattern in patterns:
        pattern.proposal, pattern.why = _propose(pattern)
    report.patterns = sorted(patterns, key=lambda p: (-p.lift, -p.support, p.text))

    # Permission proposals count *calls*, so they use the raw sequence: you
    # approved `grep` 276 times, not 200 collapsed runs of it.
    report.permissions, notes = _permissions(conn, raw, project_root)
    report.notes.extend(notes)

    if report.n_sessions < MIN_SUPPORT:
        report.notes.append(
            f"{report.n_sessions} session(s) — a sequence has to appear in "
            f"{MIN_SUPPORT} before it is a pattern rather than a coincidence")
    return report


def fingerprint(report: Report) -> str:
    payload = json.dumps({
        "project": report.project_root, "kind": report.kind,
        "patterns": [[p.text, p.support, p.count, round(p.lift, 3), p.proposal]
                     for p in report.patterns],
        "permissions": [[p.signature, p.calls, p.sessions] for p in report.permissions],
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def save(conn, report: Report) -> tuple[int, bool]:
    from . import PARSER_VERSION

    fp = fingerprint(report)
    last = conn.execute(
        "SELECT id, fingerprint FROM pattern_runs WHERE project_root IS ? AND kind = ?"
        " AND pattern_version = ? ORDER BY id DESC LIMIT 1",
        (report.project_root, report.kind, PATTERN_VERSION)).fetchone()
    if last and last["fingerprint"] == fp:
        return last["id"], False

    cur = conn.execute(
        "INSERT INTO pattern_runs (taken, project_root, kind, n_sessions, n_calls,"
        " fingerprint, pattern_version, parser_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), report.project_root, report.kind,
         report.n_sessions, report.n_calls, fp, PATTERN_VERSION, PARSER_VERSION))
    run_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO patterns (run_id, sequence, length, support, occurrences, lift,"
        " proposal, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(run_id, p.text, len(p.sequence), p.support, p.count, p.lift, p.proposal, p.why)
         for p in report.patterns])
    conn.executemany(
        "INSERT INTO pattern_occurrences (run_id, sequence, session_id, message_uuid,"
        " position, from_end) VALUES (?, ?, ?, ?, ?, ?)",
        [(run_id, p.text, o.session_id, o.message_uuid, o.position, o.from_end)
         for p in report.patterns for o in p.occurrences])
    conn.executemany(
        "INSERT INTO pattern_permissions (run_id, signature, calls, sessions, rule)"
        " VALUES (?, ?, ?, ?, ?)",
        [(run_id, p.signature, p.calls, p.sessions, p.rule) for p in report.permissions])
    conn.commit()
    return run_id, True
