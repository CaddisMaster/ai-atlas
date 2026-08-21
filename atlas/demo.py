"""A synthetic corpus, so the tool can be seen working without anybody's data.

⚠️ Two rules, and the second is the hard one.

**Nothing here is a recording.** Every transcript is generated from the model
below. No real session, prompt, command or file path from any machine appears in
it. That is what makes a demo shareable at all, given what `SECURITY.md` says
lives in a real `~/.claude`.

**The numbers are not arranged to flatter the tool.** A demo where the baseline
is confident, every pattern is a ritual and every intervention has a verdict
would misrepresent what this does with ten real sessions. So the corpus contains
what a real one contains:

- a project with enough sessions to say something, and one with two, which gets
  refused;
- a genuine behavioural change partway through, so an intervention can be found
  — and a second change too late in the corpus to measure, which is refused;
- noise that looks like a pattern and is correctly rejected by lift;
- sessions abandoned before the assistant replied;
- a subagent transcript carrying its *parent's* `sessionId`;
- an unmodelled record type, so `record_types` has something to report;
- multi-line and compound shell commands;
- a final line left half-written, because a live transcript ends mid-record.

The generator is seeded. Same seed, same corpus, so a screenshot in the README
can be reproduced by anybody.
"""

import json
import os
import random
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .paths import encode_project_dir

SEED = 20260821

MARKER = ".atlas-demo"

# The demo's own vocabulary. Invented, and deliberately not anybody's stack.
RITUAL = ["git status", "git diff", "git add", "git commit"]
NOISE = ["grep", "sed", "cat", "ls", "head"]
BUILD = ["make build", "make test"]

STATUS_DOC = """# Current status

## Where things are — 2026-07-01

Milestone 2 is next. 4 tests, all passing.

| # | Milestone | State |
|---|---|---|
| 1 | Parse the ledger format | ✅ done |
| 2 | Reconcile against the bank export | next |

See [the design notes](design.md).
"""


@dataclass
class Corpus:
    root: Path
    claude_home: Path
    projects: list[Path] = field(default_factory=list)
    sessions: int = 0
    changed_on: str = ""
    notes: list[str] = field(default_factory=list)


def _write_jsonl(path: Path, records: list[dict], truncate_last: bool = False,
                 mtime: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r) + "\n" for r in records)
    if truncate_last:
        # A transcript being written right now ends mid-record. The demo has one,
        # because that is the state ingest has to survive.
        text = text[:-40]
    path.write_text(text)
    if mtime is not None:
        # ⚠️ Real transcripts carry the mtime of the session that wrote them, and
        # `atlas now` picks the live one by mtime. Writing 26 files in the same
        # second makes "which is live" a coin toss decided by filesystem
        # granularity — the demo picked a session from the middle of the corpus.
        stamp = mtime.timestamp()
        os.utime(path, (stamp, stamp))


def _tool_use(name: str, command: str | None = None, path: str | None = None) -> dict:
    block: dict = {"type": "tool_use", "name": name, "input": {}}
    if command is not None:
        block["input"]["command"] = command
    if path is not None:
        block["input"]["file_path"] = path
    return block


def _session_records(rng: random.Random, session_id: str, cwd: str, start: datetime,
                     calls: list[dict], turns: int, abandoned: bool = False) -> list[dict]:
    records: list[dict] = [{
        "type": "user", "uuid": f"{session_id}-u0", "sessionId": session_id, "cwd": cwd,
        "timestamp": start.isoformat().replace("+00:00", "Z"),
        "message": {"role": "user", "content": "pick up where we left off"},
    }]
    if abandoned:
        # Typed and walked away. Two of thirteen real sessions look like this.
        return records

    when = start
    # ⚠️ Contiguous chunks, not a strided slice. `calls[turn::turns]` scattered
    # each ritual across every turn, and `patterns` duly reported rotated
    # fragments — `git diff → git status → git add → git diff` — because that is
    # genuinely what the generated transcript said. A generator bug looks
    # exactly like a detector bug from the outside.
    per_turn = max(1, -(-len(calls) // turns)) if turns else 0
    for turn in range(turns):
        when += timedelta(minutes=rng.uniform(0.5, 4.0))
        mine = calls[turn * per_turn:(turn + 1) * per_turn]
        records.append({
            "type": "assistant", "uuid": f"{session_id}-a{turn}",
            "parentUuid": f"{session_id}-u{turn}", "sessionId": session_id, "cwd": cwd,
            "timestamp": when.isoformat().replace("+00:00", "Z"),
            "message": {"role": "assistant",
                        "usage": {"input_tokens": rng.randint(20, 200),
                                  "output_tokens": rng.randint(200, 2000),
                                  "cache_read_input_tokens": rng.randint(20_000, 90_000),
                                  "cache_creation_input_tokens": rng.randint(0, 4_000)},
                        "content": mine or [{"type": "text", "text": "…"}]},
        })
        when += timedelta(minutes=rng.uniform(0.5, 3.0))
        records.append({
            "type": "user", "uuid": f"{session_id}-u{turn + 1}",
            "parentUuid": f"{session_id}-a{turn}", "sessionId": session_id, "cwd": cwd,
            "timestamp": when.isoformat().replace("+00:00", "Z"),
            "message": {"role": "user", "content": "carry on"},
        })
    records.append({"type": "mode", "mode": "normal", "sessionId": session_id})
    # Unmodelled on purpose: format drift has to show up as a number.
    records.append({"type": "demo-only-record", "sessionId": session_id,
                    "timestamp": when.isoformat().replace("+00:00", "Z")})
    return records


def _calls(rng: random.Random, *, ritual: bool, length: int) -> list[dict]:
    calls: list[dict] = []
    for _ in range(length):
        roll = rng.random()
        if ritual and roll < 0.28:
            # The habit the demo wants `patterns` to find, spread over real
            # calls rather than one compound command.
            for step in RITUAL:
                calls.append(_tool_use("Bash", command=f"{step} -q"))
            # ⚠️ Always something else afterwards. Back-to-back rituals make the
            # sequence a *cycle*, and every rotation of it then scores as its own
            # pattern — four near-identical rows at the top of the screen. Real
            # work interleaves; the generator has to as well.
            calls.append(_tool_use("Read", path="docs/design.md"))
        elif roll < 0.55:
            first, second = rng.sample(NOISE, 2)
            calls.append(_tool_use("Bash", command=f"{first} -n 'x' src/ledger.py"))
            calls.append(_tool_use("Bash", command=f"cd src\n{second} report.csv"))
        elif roll < 0.7:
            calls.append(_tool_use("Bash", command=f"{rng.choice(BUILD)} && echo done"))
        elif roll < 0.85:
            calls.append(_tool_use("Edit", path=f"src/{rng.choice(('ledger', 'report'))}.py"))
        else:
            calls.append(_tool_use("Read", path="docs/design.md"))
    return calls


def _project(root: Path, name: str, *, configured: bool) -> Path:
    project = root / "work" / name
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "ledger.py").write_text("# demo\n")
    (project / "CLAUDE.md").write_text(f"# {name}\n\nSynthetic project. Not real work.\n")
    if not configured:
        return project

    claude = project / ".claude"
    (claude / "agents").mkdir(parents=True, exist_ok=True)
    (claude / "commands").mkdir(parents=True, exist_ok=True)
    (claude / "skills" / "reconcile").mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text(json.dumps({
        "permissions": {"allow": ["Bash(make build:*)", "Bash(git status:*)"],
                        "deny": ["Bash(git push --force:*)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command",
                                       "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check.sh"}]}]},
    }, indent=2) + "\n")
    (claude / "agents" / "ledger-auditor.md").write_text("---\nname: ledger-auditor\n---\n")
    (claude / "commands" / "reconcile.md").write_text("Reconcile the ledger.\n")
    (claude / "skills" / "reconcile" / "SKILL.md").write_text("---\nname: reconcile\n---\n")
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "status.md").write_text(STATUS_DOC)
    (project / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added — milestone 2, reconciliation\n\n- Done.\n")
    return project


def _git_init(project: Path) -> bool:
    """A repository, so `handoff` has something to reconcile against.

    The status document is deliberately stale — it says milestone 2 is next
    while the changelog says it landed, and it links a file that does not exist.
    """
    env = {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid",
           "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid",
           "GIT_AUTHOR_DATE": "2026-07-20T10:00:00", "GIT_COMMITTER_DATE": "2026-07-20T10:00:00",
           "PATH": "/usr/bin:/bin"}
    try:
        for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "demo")):
            subprocess.run(["git", "-C", str(project), *args], check=True,
                           capture_output=True, env=env)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def generate(root: Path, seed: int = SEED, sessions: int = 20) -> Corpus:
    """Build the whole corpus under ``root``. Same seed, same corpus."""
    rng = random.Random(seed)
    root = Path(root)
    claude = root / ".claude"
    (claude / "projects").mkdir(parents=True, exist_ok=True)
    # A marker, so `--fresh` can tell a demo directory from somebody's actual
    # work before deleting anything.
    (root / MARKER).write_text("generated by `atlas demo` — safe to delete\n")
    (claude / "settings.json").write_text(json.dumps(
        {"model": "opus", "permissions": {"deny": ["Read(./.env)"]}}, indent=2) + "\n")

    busy = _project(root, "acme-invoices", configured=True)
    # The sibling file, holding an "always allow" answer — a permission grant
    # that appears in no settings.json in any scope.
    (root / ".claude.json").write_text(json.dumps({
        "projects": {str(root / "work" / "acme-invoices"): {
            "allowedTools": ["Bash(make build:*)"], "hasTrustDialogAccepted": True}},
    }, indent=2) + "\n")
    tiny = _project(root, "tiny-script", configured=False)
    corpus = Corpus(root=root, claude_home=claude, projects=[busy, tiny])
    corpus.notes.append("git repository" if _git_init(busy) else "no git (git unavailable)")

    start = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    # The change: from the halfway point the ritual is done by one command
    # instead of four calls, so sessions get shorter. A real effect, generated
    # on purpose — the tool still has to decide whether it can see it.
    halfway = sessions // 2
    corpus.changed_on = (start + timedelta(days=halfway)).isoformat()

    for index in range(sessions):
        session_id = f"demo{index:04d}-0000-4000-8000-{index:012d}"
        began = start + timedelta(days=index, hours=rng.uniform(0, 6))
        before = index < halfway
        calls = _calls(rng, ritual=before, length=rng.randint(6, 14) if before else rng.randint(4, 9))
        turns = max(3, len(calls) // 2)
        directory = claude / "projects" / encode_project_dir(busy)
        live = index == sessions - 1
        _write_jsonl(directory / f"{session_id}.jsonl",
                     _session_records(rng, session_id, str(busy), began, calls, turns),
                     truncate_last=live,
                     # The last one is still being written, so it is "now".
                     mtime=datetime.now(UTC) if live else began + timedelta(hours=1))
        corpus.sessions += 1

        if index in (2, 11):
            # A subagent, one level deeper, carrying its PARENT's sessionId.
            _write_jsonl(directory / session_id / "subagents" / f"agent-{index:04x}.jsonl",
                         _session_records(rng, session_id, str(busy),
                                          began + timedelta(minutes=5),
                                          _calls(rng, ritual=False, length=3), 3),
                         mtime=began + timedelta(minutes=30))
            corpus.sessions += 1

    for index in range(2):
        session_id = f"tiny{index:04d}-0000-4000-8000-{index:012d}"
        _write_jsonl(claude / "projects" / encode_project_dir(tiny) / f"{session_id}.jsonl",
                     _session_records(rng, session_id, str(tiny),
                                      start + timedelta(days=index),
                                      _calls(rng, ritual=False, length=4), 3),
                     mtime=start + timedelta(days=index, hours=1))
        corpus.sessions += 1

    # Abandoned: a prompt typed, no reply. Two of thirteen real sessions.
    for index in range(2):
        session_id = f"gone{index:04d}-0000-4000-8000-{index:012d}"
        _write_jsonl(claude / "projects" / encode_project_dir(busy) / f"{session_id}.jsonl",
                     _session_records(rng, session_id, str(busy),
                                      start + timedelta(days=3 + index), [], 0, abandoned=True),
                     mtime=start + timedelta(days=3 + index))
        corpus.sessions += 1

    return corpus
