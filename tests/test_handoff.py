"""Handoff acceptance tests.

The feature exists because `docs/status.md` is the file most likely to be wrong
and the only one nothing forces to be right. So the two things that matter are
symmetrical: it must find every contradiction, and it must report **nothing**
when the document is current. A handoff check that cries wolf gets ignored, and
an ignored check is worse than no check — it looks like evidence.
"""

import subprocess

import pytest

from atlas.handoff import STALE, UNKNOWN, run, save

STATUS = """# Current status

## Where things are — 2026-08-20

```
9 tests · ruff clean
```

## The roadmap

| # | Milestone | State |
|---|---|---|
| 1 | Scaffold + ingest | ✅ done |
| 2 | Config resolution | next |

See [the architecture](architecture.md).
"""

CHANGELOG = """# Changelog

## [Unreleased]

### Added — milestone 1, ingest

- Ingest.
"""


def _git(root, *args, when="2026-08-20T12:00:00"):
    env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "PATH": "/usr/bin:/bin"}
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True, env=env)


@pytest.fixture
def fake_repo(tmp_path):
    """A repository whose status document is accurate as of its last commit."""
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "status.md").write_text(STATUS)
    (root / "docs" / "architecture.md").write_text("# Architecture\n")
    (root / "CHANGELOG.md").write_text(CHANGELOG)
    (root / "app.py").write_text("x = 1\n")

    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def nine(_root):
    """Stand-in for the test collector, so these tests do not run pytest."""
    return 9


def stale(report):
    return {f.check for f in report.findings if f.state == STALE}


def test_a_current_status_document_reports_nothing_stale(fake_repo):
    report = run(fake_repo, counter=nine)
    assert stale(report) == set()
    assert report.findings, "silence must come from checks passing, not from no checks"


def test_a_document_older_than_the_repository_is_stale(fake_repo):
    (fake_repo / "app.py").write_text("x = 2\n")
    (fake_repo / "CHANGELOG.md").write_text(CHANGELOG + "- More.\n")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "later work", when="2026-08-25T09:00:00")

    report = run(fake_repo, counter=nine)
    assert "date" in stale(report)
    finding = next(f for f in report.findings if f.check == "date")
    assert finding.claim == "2026-08-20" and "2026-08-25" in finding.actual
    assert finding.source.endswith("status.md:3"), "a finding must name the line it came from"


def test_a_milestone_the_changelog_says_landed_cannot_still_be_next(fake_repo):
    """The changelog is the better witness: its entry is written in the same
    commit as the change, while a roadmap row is updated when somebody
    remembers."""
    (fake_repo / "CHANGELOG.md").write_text(
        CHANGELOG.replace("### Added — milestone 1, ingest",
                          "### Added — milestone 2, config resolution\n\n- Config.\n\n"
                          "### Added — milestone 1, ingest"))
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "milestone 2")

    report = run(fake_repo, counter=nine)
    finding = next(f for f in report.findings if f.check == "milestone")
    assert finding.subject.startswith("2 —") and finding.claim == "next"
    assert finding.state == STALE


def test_a_milestone_named_in_prose_has_not_landed(fake_repo):
    """"…which is what milestone 6 will compare" is a plan, not a claim.

    Reading the whole `[Unreleased]` section rather than its headings turned
    that sentence into "milestone 6 has landed", and handoff reported an empty
    roadmap row as stale. It found this in its own repository, one commit after
    the sentence was written.
    """
    (fake_repo / "CHANGELOG.md").write_text(
        CHANGELOG + "\n- Stores what milestone 2 will compare against later.\n")
    (fake_repo / "docs" / "status.md").write_text(
        STATUS.replace("| 2 | Config resolution | next |",
                       "| 2 | Config resolution | next |\n| 6 | Interventions | |"))
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "prose")

    report = run(fake_repo, counter=nine)
    assert stale(report) == set(), "a milestone mentioned in prose has not landed"


def test_a_test_count_pytest_disagrees_with_is_stale(fake_repo):
    report = run(fake_repo, counter=lambda _root: 27)
    finding = next(f for f in report.findings if f.check == "tests")
    assert (finding.claim, finding.state) == ("9", STALE)
    assert "27" in finding.actual


def test_a_per_file_test_count_is_not_read_as_a_repository_total(fake_repo):
    """"`tests/test_design_system.py` (10 tests)" counts one file.

    Comparing it against the repository total reports a contradiction that is
    not there, and a check that invents staleness gets switched off. Found
    against a real sibling project.
    """
    doc = fake_repo / "docs" / "status.md"
    doc.write_text(STATUS + "\n`tests/test_design_system.py` (10 tests) covers the palette.\n")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "note")

    report = run(fake_repo, counter=nine)
    counts = [f for f in report.findings if f.check == "tests"]
    assert [f.claim for f in counts] == ["9"]
    assert stale(report) == set()


def test_pytest_that_cannot_be_run_is_unknown_not_stale(fake_repo):
    """A count we could not take is not a count that disagrees."""
    report = run(fake_repo, counter=lambda _root: None)
    finding = next(f for f in report.findings if f.check == "tests")
    assert finding.state == UNKNOWN
    assert stale(report) == set()


def test_a_broken_relative_link_is_found(fake_repo):
    (fake_repo / "docs" / "status.md").write_text(
        STATUS.replace("(architecture.md)", "(architecture-moved.md)"))
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "rename")

    report = run(fake_repo, counter=nine)
    broken = [f for f in report.findings if f.check == "link" and f.state == STALE]
    assert any(f.subject == "architecture-moved.md" for f in broken)
    assert any(f.source.endswith("docs/status.md:16") for f in broken)


def test_code_committed_after_the_changelog_is_flagged(fake_repo):
    """The Stop hook catches an omission inside a session. This catches the one
    that got through anyway."""
    (fake_repo / "app.py").write_text("x = 3\n")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "undocumented change")

    report = run(fake_repo, counter=nine)
    finding = next(f for f in report.findings if f.check == "changelog")
    assert finding.state == STALE and "app.py" in finding.actual


def test_a_v_prefixed_tag_is_still_a_version(fake_repo):
    """Regression: `\\b` never matches between `v` and `0`, so every `v0.8.0`
    tag on the sibling project parsed as no version at all and the check
    crashed. This project has no tags, so only real data could find it.
    """
    _git(fake_repo, "tag", "v0.2.0")

    report = run(fake_repo, counter=nine)
    finding = next(f for f in report.findings if f.check == "version")
    assert finding.claim == "v0.2.0 is tagged"
    assert finding.state == STALE, "the document never mentions the newest tag"

    doc = fake_repo / "docs" / "status.md"
    doc.write_text(STATUS.replace("# Current status", "# Current status — v0.2.0 shipped"))
    finding = next(f for f in run(fake_repo, counter=nine).findings if f.check == "version")
    assert finding.state != STALE


def test_a_dependency_version_is_not_compared_against_a_tag(fake_repo):
    """A status document mentions the versions of things it depends on. The
    first run of this check against a real repository compared a Postgres
    version with a git tag and declared the document stale."""
    _git(fake_repo, "tag", "v0.2.0")
    doc = fake_repo / "docs" / "status.md"
    doc.write_text(STATUS.replace("# Current status",
                                  "# Current status — v0.2.0, on PostgreSQL 10.15.0"))

    report = run(fake_repo, counter=nine)
    assert stale(report) == set()


def test_a_directory_that_is_not_a_repository_is_unknown_not_stale(tmp_path):
    report = run(tmp_path, counter=nine)
    assert [f.state for f in report.findings] == [UNKNOWN]
    assert not report.stale


def test_an_unchanged_rerun_is_not_a_new_run(conn, fake_repo):
    first, is_new = save(conn, run(fake_repo, counter=nine))
    assert is_new
    again, is_new = save(conn, run(fake_repo, counter=nine))
    assert (again, is_new) == (first, False)

    (fake_repo / "docs" / "status.md").write_text(STATUS + "\n27 tests now.\n")
    third, is_new = save(conn, run(fake_repo, counter=nine))
    assert is_new and third != first
