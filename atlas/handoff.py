"""Reconcile a project's status document against the repository.

`docs/status.md` is read at the start of every session and is wrong more often
than any other file, because it is the only one nothing forces to be updated.
Code has tests, the changelog has a hook, the status document has a habit.

So this checks the document against things that cannot be talked into agreeing:
git, the changelog, the test collector, the filesystem. Every check is
deterministic — it counts or compares, it never judges — and every finding names
the line it came from so the reader can disagree with it.

⚠️ Three states, as everywhere else in this codebase. A check that could not
gather its evidence reports ``unknown``, never ``ok``. A status document is not
current because we failed to look.

⚠️ Offline by default. Everything here reads the working tree, except
``--github``, which shells out to `gh` and is the only part of ai-atlas that
touches the network. See SECURITY.md.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

STALE, OK, UNKNOWN = "stale", "ok", "unknown"

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
TEST_COUNT = re.compile(r"\b(\d+)\s+tests?\b", re.IGNORECASE)
NAMES_A_FILE = re.compile(r"\S+\.(py|md|sh|sql)\b")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# `### Added — milestone 2, config resolution` in the changelog's Unreleased
# section is the claim that milestone 2 has landed.
#
# ⚠️ Headings only. The body of that section is prose, and prose mentions
# milestones that have *not* landed — "which is what milestone 6 will compare".
# Scanning the whole section read that as a claim and reported milestone 6 as
# done while it was still an empty roadmap row. Found by running handoff against
# this repository one commit after writing the sentence.
CHANGELOG_MILESTONE = re.compile(r"^#{2,4}\s.*milestone\s+(\d+)", re.IGNORECASE | re.MULTILINE)
# `| 2 | Config resolution | ✅ done |` in the status document's roadmap.
ROADMAP_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|")
DONE = re.compile(r"done|shipped|✅", re.IGNORECASE)

CODE_SUFFIXES = {".py", ".sql", ".sh", ".toml", ".ini"}


@dataclass(frozen=True)
class Finding:
    check: str
    subject: str
    claim: str
    actual: str
    state: str
    source: str = ""     # "docs/status.md:9"

    @property
    def is_stale(self) -> bool:
        return self.state == STALE


@dataclass
class Report:
    repo: Path
    status_path: Path | None = None
    head: str = ""
    findings: list[Finding] = field(default_factory=list)

    @property
    def stale(self) -> list[Finding]:
        return [f for f in self.findings if f.state == STALE]

    @property
    def unknown(self) -> list[Finding]:
        return [f for f in self.findings if f.state == UNKNOWN]


class Repo:
    """Git facts, gathered by asking git. Never raises: a failure is ``None``."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def git(self, *args: str) -> str | None:
        try:
            done = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    def is_repo(self) -> bool:
        return self.git("rev-parse", "--git-dir") is not None

    def head(self) -> str | None:
        return self.git("rev-parse", "--short", "HEAD")

    def last_commit_date(self) -> str | None:
        return self.git("log", "-1", "--format=%ad", "--date=short")

    def tags(self) -> list[str]:
        out = self.git("tag", "--list")
        return out.splitlines() if out else []

    def files_changed_since_last_touch(self, path: str) -> list[str]:
        """Files changed by commits made after ``path`` was last committed."""
        last = self.git("log", "-1", "--format=%H", "--", path)
        if not last:
            return []
        out = self.git("log", "--name-only", "--format=", f"{last}..HEAD")
        return sorted({line for line in (out or "").splitlines() if line})


def find_status_doc(repo: Path) -> Path | None:
    for candidate in ("docs/status.md", "STATUS.md", "docs/STATUS.md", "status.md"):
        path = repo / candidate
        if path.is_file():
            return path
    return None


# ⚠️ The `v` in `v0.8.0` is a word character, so a leading `\b` never matches
# after it and every tag on the sibling project parsed as no version at all.
# Found by running against a real repository, which is the only reason it was
# found: this project has no tags yet. Guarded by
# test_a_v_prefixed_tag_is_still_a_version.
VERSION = re.compile(r"(?<![\w.])v?(\d+)\.(\d+)\.(\d+)(?![\w.])")


def _versions(text: str) -> list[tuple[int, int, int]]:
    return [tuple(int(p) for p in m) for m in VERSION.findall(text)]


def _line_of(text: str, needle: str) -> int:
    for n, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return n
    return 0


def _ref(path: Path, repo: Path, line: int = 0) -> str:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        rel = path
    return f"{rel}:{line}" if line else str(rel)


def check_date(doc_text: str, doc: Path, repo: Repo) -> list[Finding]:
    """The newest date claimed against the date of the last commit.

    A status document written on the 20th and a repository last touched on the
    21st is the ordinary way this file goes wrong, and it is invisible from
    inside the document.
    """
    dates = sorted(DATE.findall(doc_text))
    if not dates:
        return []
    claimed = dates[-1]
    actual = repo.last_commit_date()
    if actual is None:
        return [Finding("date", "as-of date", claimed, "git did not answer", UNKNOWN,
                        _ref(doc, repo.root, _line_of(doc_text, claimed)))]
    state = STALE if actual > claimed else OK
    return [Finding("date", "as-of date", claimed, f"last commit {actual}", state,
                    _ref(doc, repo.root, _line_of(doc_text, claimed)))]


def check_milestones(doc_text: str, doc: Path, repo: Repo) -> list[Finding]:
    """Roadmap rows against what the changelog says has landed.

    The changelog is the better witness: an entry there is written in the same
    commit as the change, while a roadmap row is updated when somebody
    remembers. Only the direction that matters is reported — the changelog says
    it landed, the roadmap does not.
    """
    changelog = repo.root / "CHANGELOG.md"
    try:
        text = changelog.read_text()
    except OSError:
        return []
    unreleased = text.split("## [Unreleased]", 1)
    if len(unreleased) < 2:
        return []
    body = re.split(r"\n## ", unreleased[1], maxsplit=1)[0]
    landed = {int(n) for n in CHANGELOG_MILESTONE.findall(body)}
    if not landed:
        return []

    findings = []
    for line_no, line in enumerate(doc_text.splitlines(), start=1):
        row = ROADMAP_ROW.match(line.strip())
        if not row:
            continue
        number, name, state = int(row.group(1)), row.group(2).strip(), row.group(3).strip()
        if number in landed and not DONE.search(state):
            findings.append(Finding(
                "milestone", f"{number} — {name}", state or "(blank)",
                "CHANGELOG [Unreleased] says it landed", STALE,
                _ref(doc, repo.root, line_no)))
    if not findings:
        landed_list = ", ".join(str(n) for n in sorted(landed))
        findings.append(Finding("milestone", f"milestone(s) {landed_list}",
                                "in the changelog", "marked done in the roadmap", OK,
                                _ref(doc, repo.root)))
    return findings


def check_versions(doc_text: str, doc: Path, repo: Repo) -> list[Finding]:
    """Does the status document mention the newest release tag?

    ⚠️ Not "is the newest version in the document at least the newest tag". A
    document mentions the versions of everything it depends on — the first run
    of this check against a real repository compared a Postgres version against
    a git tag and called the document stale. The only version this project can
    reason about is one that exists as a tag on this repository, and the only
    deterministic question about it is whether the document says it.
    """
    tagged = _versions("\n".join(repo.tags()))
    if not tagged:
        return []
    newest = ".".join(str(p) for p in max(tagged))
    mentioned = re.search(rf"(?<![\w.])v?{re.escape(newest)}(?![\w.])", doc_text) is not None
    return [Finding("version", "newest release tag", f"v{newest} is tagged",
                    "mentioned in the document" if mentioned else "the document never mentions it",
                    OK if mentioned else STALE, _ref(doc, repo.root))]


def collect_test_count(repo: Path) -> int | None:
    """How many tests pytest can see. ``None`` when pytest could not be run.

    Prefers `.venv/bin/pytest` for the same reason `test.sh` does: this project
    is not in a container, so a bare `pytest` is whatever the shell happens to
    have.
    """
    venv = repo / ".venv" / "bin" / "pytest"
    for command in ([str(venv)] if venv.exists() else []) + ["pytest"]:
        try:
            done = subprocess.run([command, "--collect-only", "-q"], cwd=repo,
                                  capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"(\d+)\s+tests?\s+collected", done.stdout)
        if match:
            return int(match.group(1))
        if "no tests" in done.stdout.lower() or done.returncode == 5:
            return 0
    return None


def check_test_count(doc_text: str, doc: Path, repo: Repo,
                     counter=collect_test_count) -> list[Finding]:
    """"27 tests" is a claim about the repository, and pytest settles it.

    ⚠️ Only when it *is* about the repository. A line naming a file —
    "`tests/test_design_system.py` (10 tests)" — is counting that file, and
    comparing it against the total would report a contradiction that is not
    there. Reporting a false staleness is worse than missing a real one: the
    whole point is a claim the reader can trust without re-deriving it.
    """
    claims = []
    for line_no, line in enumerate(doc_text.splitlines(), start=1):
        if NAMES_A_FILE.search(line):
            continue
        for match in TEST_COUNT.finditer(line):
            claims.append((int(match.group(1)), line_no))
    if not claims:
        return []
    actual = counter(repo.root)
    findings = []
    for claimed, line_no in claims:
        if actual is None:
            findings.append(Finding("tests", "test count", str(claimed),
                                    "pytest could not be run", UNKNOWN,
                                    _ref(doc, repo.root, line_no)))
        else:
            findings.append(Finding("tests", "test count", str(claimed),
                                    f"{actual} collected",
                                    STALE if claimed != actual else OK,
                                    _ref(doc, repo.root, line_no)))
    return findings


def check_links(repo: Repo, docs: list[Path]) -> list[Finding]:
    """Relative links that point at nothing.

    Cheap, and it catches the specific rot that follows a rename: the document
    still describes a file that moved, and nothing else notices.
    """
    findings = []
    checked = 0
    for path in docs:
        try:
            text = path.read_text()
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for target in MD_LINK.findall(line):
                target = target.split()[0]
                if target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                checked += 1
                if not (path.parent / target.split("#")[0]).exists():
                    findings.append(Finding("link", target, "linked", "no such file", STALE,
                                            _ref(path, repo.root, line_no)))
    findings.append(Finding("link", f"{checked} relative link(s) in {len(docs)} document(s)",
                            "resolve", f"{len(findings)} broken",
                            STALE if findings else OK))
    return findings


def check_changelog_lag(repo: Repo) -> list[Finding]:
    """Code committed after the changelog was last touched.

    The `Stop` hook catches an omission within a session. This catches the one
    that got through anyway, which is the only kind still worth reporting.
    """
    if not (repo.root / "CHANGELOG.md").exists():
        return []
    changed = repo.files_changed_since_last_touch("CHANGELOG.md")
    code = [f for f in changed if Path(f).suffix in CODE_SUFFIXES]
    if not code:
        return [Finding("changelog", "CHANGELOG.md", "current",
                        "no code committed since it was last touched", OK, "CHANGELOG.md")]
    return [Finding("changelog", "CHANGELOG.md", "current",
                    f"{len(code)} code file(s) changed since it was last committed: "
                    + ", ".join(code[:4]) + ("…" if len(code) > 4 else ""),
                    STALE, "CHANGELOG.md")]


def check_github(doc_text: str, doc: Path, repo: Repo) -> list[Finding]:
    """Open pull requests the status document does not mention.

    ⚠️ The only network call in ai-atlas, and it is opt-in for that reason. It
    sends a repository name to GitHub and nothing read out of ~/.claude.
    """
    try:
        done = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title"],
            cwd=repo.root, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return [Finding("github", "open pull requests", "—", "gh could not be run", UNKNOWN)]
    if done.returncode != 0:
        return [Finding("github", "open pull requests", "—",
                        f"gh failed: {done.stderr.strip()[:80]}", UNKNOWN)]
    try:
        prs = json.loads(done.stdout or "[]")
    except json.JSONDecodeError:
        return [Finding("github", "open pull requests", "—", "gh returned no JSON", UNKNOWN)]

    findings = []
    for pr in prs:
        mentioned = f"#{pr['number']}" in doc_text
        findings.append(Finding(
            "github", f"PR #{pr['number']}", pr["title"][:60],
            "mentioned" if mentioned else "open and not mentioned",
            OK if mentioned else STALE, _ref(doc, repo.root)))
    return findings


def run(repo_root: Path | str, status: Path | None = None, github: bool = False,
        counter=collect_test_count) -> Report:
    repo = Repo(Path(repo_root))
    report = Report(repo=repo.root)

    if not repo.is_repo():
        report.findings.append(Finding("git", "repository", str(repo.root),
                                       "not a git repository", UNKNOWN))
        return report
    report.head = repo.head() or ""

    doc = Path(status) if status else find_status_doc(repo.root)
    report.status_path = doc
    docs = sorted({*repo.root.glob("*.md"), *repo.root.glob("docs/**/*.md")})
    report.findings.extend(check_links(repo, docs))
    report.findings.extend(check_changelog_lag(repo))

    if doc is None:
        report.findings.append(Finding("status", "status document", "—",
                                       "none found (docs/status.md, STATUS.md)", UNKNOWN))
        return report

    text = doc.read_text()
    report.findings.extend(check_date(text, doc, repo))
    report.findings.extend(check_milestones(text, doc, repo))
    report.findings.extend(check_versions(text, doc, repo))
    report.findings.extend(check_test_count(text, doc, repo, counter=counter))
    if github:
        report.findings.extend(check_github(text, doc, repo))
    return report


def fingerprint(report: Report) -> str:
    import hashlib
    payload = json.dumps([[f.check, f.subject, f.claim, f.actual, f.state, f.source]
                          for f in report.findings], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def save(conn, report: Report) -> tuple[int, bool]:
    """Store a run, so "how long has this been stale" is answerable later."""
    from . import PARSER_VERSION

    fp = fingerprint(report)
    last = conn.execute(
        "SELECT id, fingerprint FROM handoff_snap WHERE repo = ? ORDER BY id DESC LIMIT 1",
        (str(report.repo),)).fetchone()
    if last and last["fingerprint"] == fp:
        return last["id"], False

    cur = conn.execute(
        "INSERT INTO handoff_snap (taken, repo, head, status_path, fingerprint, parser_version)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), str(report.repo), report.head,
         str(report.status_path) if report.status_path else None, fp, PARSER_VERSION))
    snap_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO handoff_findings (snap_id, check_name, subject, claim, actual, state, source)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(snap_id, f.check, f.subject, f.claim, f.actual, f.state, f.source)
         for f in report.findings])
    conn.commit()
    return snap_id, True
