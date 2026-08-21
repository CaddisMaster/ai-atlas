"""Scope resolution acceptance tests.

The first test is the regression for the wrong answer that motivated the whole
project: reading `~/.claude/settings.json` alone and reporting that the user had
no hooks, no permission rules, no skills and no slash commands, while a project
scope one directory away held all four. See docs/disproven.md and
docs/decisions/0001.
"""

import json
import os
from pathlib import Path

import pytest

from atlas.config import ABSENT, PRESENT, UNKNOWN, resolve, save, split_rule
from atlas.paths import project_root_for


def _resolve(project, home, enterprise=None):
    """Resolve with the enterprise path pinned, so tests never read /etc."""
    return resolve(project, root=home, enterprise=enterprise or home / "nonexistent-policy.json")


def test_project_scope_is_not_missed_by_a_user_scope_read(fake_project, fake_home):
    """The disproven claim, as a test.

    A read of the user's settings.json alone finds one model key and no
    permissions block worth the name. Every one of these lives in the project.
    """
    res = _resolve(fake_project, fake_home)

    assert {i.name for i in res.of_kind("agent")} == {"test-first", "sweeper"}
    assert {i.name for i in res.of_kind("command")} == {"/wrap"}
    assert {i.name for i in res.of_kind("skill")} == {"verify"}
    assert {i.name for i in res.of_kind("hook")} == {"Stop"}
    assert len([r for r in res.rules if r.scope == "project"]) == 4

    for kind in ("agent", "command", "skill", "hook"):
        assert {i.scope for i in res.of_kind(kind)} == {"project"}


def test_every_fact_carries_its_source(fake_project, fake_home):
    """A setting shown without its provenance is how the original mistake reads."""
    res = _resolve(fake_project, fake_home)
    for fact in [*res.items, *res.rules]:
        assert fact.scope and fact.source_path


def test_a_skill_is_named_for_its_directory_not_its_file(fake_project, fake_home):
    """Every skill file is called SKILL.md, so the filename names nothing."""
    skill = _resolve(fake_project, fake_home).of_kind("skill")[0]
    assert skill.name == "verify"
    assert skill.source_path.endswith("skills/verify/SKILL.md")


def test_permission_rules_accumulate_across_scopes(fake_project, fake_home):
    """Permissions are additive: a project's rules do not replace the user's."""
    res = _resolve(fake_project, fake_home)
    by_scope = {}
    for rule in res.rules:
        by_scope.setdefault(rule.scope, []).append(rule.pattern)

    assert "Read(./.env)" in by_scope["user"]
    assert "Bash(./test.sh)" in by_scope["project"]
    # ⚠️ and the one nobody looks for: an "always allow" answer, which is stored
    # in ~/.claude.json and appears in no settings.json in any scope.
    assert by_scope["dynamic"] == ["Bash(npm test:*)"]


def test_a_project_agent_shadows_a_user_agent_of_the_same_name(fake_project, fake_home):
    """The lower-precedence one is kept, marked, and still reported.

    Dropping it would make "you defined this twice" unanswerable, which is a
    thing worth being told.
    """
    user_agent = fake_home / "agents" / "sweeper.md"
    user_agent.parent.mkdir(parents=True, exist_ok=True)
    user_agent.write_text("---\nname: sweeper\n---\n")

    res = _resolve(fake_project, fake_home)
    sweepers = {i.scope: i.shadowed for i in res.of_kind("agent") if i.name == "sweeper"}
    assert sweepers == {"project": False, "user": True}
    assert len(res.of_kind("agent", include_shadowed=False)) == 2


def test_a_malformed_settings_file_is_unknown_not_absent(fake_project, fake_home):
    """A syntax error is a failure to read, and reporting it as "not configured"
    is exactly how a confident false claim gets made."""
    (fake_project / ".claude" / "settings.local.json").write_text("{ oops")

    res = _resolve(fake_project, fake_home)
    scope = next(s for s in res.scopes if s.path.endswith("settings.local.json"))
    assert scope.state == UNKNOWN
    assert "malformed" in scope.detail
    assert res.scope_state("local") == UNKNOWN


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
def test_an_unreadable_enterprise_policy_is_unknown_not_absent(fake_project, fake_home, tmp_path):
    """Managed policy is the scope a user is most likely to be unable to read,
    and the one whose rules they can least afford to be told they do not have."""
    policy = tmp_path / "managed-settings.json"
    policy.write_text(json.dumps({"permissions": {"deny": ["Bash(curl:*)"]}}))
    policy.chmod(0o000)

    res = _resolve(fake_project, fake_home, enterprise=policy)
    assert res.scope_state("enterprise") == UNKNOWN
    assert not [r for r in res.rules if r.scope == "enterprise"]


def test_a_missing_file_is_absent(fake_project, fake_home):
    res = _resolve(fake_project, fake_home)
    assert res.scope_state("enterprise") == ABSENT
    assert res.scope_state("project") == PRESENT


def test_command_line_flags_are_always_unknown(fake_project, fake_home):
    """`claude --permission-mode ...` leaves no trace on disk. Assuming a scope
    we cannot see is empty is the original bug wearing a different hat."""
    res = _resolve(fake_project, fake_home)
    assert res.scope_state("cli") == UNKNOWN


def test_places_looked_are_recorded_even_when_empty(fake_project, fake_home):
    """"Never configured" is a claim about where we looked, so where we looked
    is evidence and has to survive into the snapshot."""
    res = _resolve(fake_project, fake_home)
    looked = {s.path for s in res.scopes}
    assert str(fake_home / "agents") in looked
    assert str(fake_home / "commands") in looked
    assert str(fake_project / ".mcp.json") in looked


@pytest.mark.parametrize("pattern,expected", [
    ("Bash(git push --force:*)", ("Bash", "git push --force:*")),
    ("Read(./*.db)", ("Read", "./*.db")),
    ("WebFetch", ("WebFetch", None)),
    ("mcp__linear__create_issue", ("mcp__linear__create_issue", None)),
])
def test_rules_split_into_tool_and_argument(pattern, expected):
    assert split_rule(pattern) == expected


def test_an_unchanged_rerun_is_not_a_new_snapshot(conn, fake_project, fake_home):
    """Config is stored as history. Re-running the command is not history."""
    first, is_new = save(conn, _resolve(fake_project, fake_home))
    assert is_new
    again, is_new = save(conn, _resolve(fake_project, fake_home))
    assert (again, is_new) == (first, False)

    (fake_project / ".claude" / "commands" / "ship.md").write_text("Ship it.\n")
    third, is_new = save(conn, _resolve(fake_project, fake_home))
    assert is_new and third != first


def test_a_snapshot_keeps_scope_provenance(conn, fake_project, fake_home):
    snap_id, _ = save(conn, _resolve(fake_project, fake_home))
    rows = conn.execute(
        "SELECT kind, name, scope FROM config_items WHERE snap_id = ? AND kind = 'skill'",
        (snap_id,),
    ).fetchall()
    assert [(r["name"], r["scope"]) for r in rows] == [("verify", "project")]

    unknown = conn.execute(
        "SELECT scope FROM config_scopes WHERE snap_id = ? AND state = 'unknown'", (snap_id,),
    ).fetchall()
    assert [r["scope"] for r in unknown] == ["cli"]


def test_a_project_directory_name_is_matched_not_decoded():
    """`-home-sean-personal-projects` could be two different paths and the name
    does not say which. So the root is taken from `cwd` and confirmed by
    encoding it back; a guess that cannot be confirmed returns nothing."""
    assert project_root_for("/home/sean/personal-projects/app/src",
                            "-home-sean-personal-projects-app") == Path(
                                "/home/sean/personal-projects/app")
    assert project_root_for("/somewhere/else", "-home-sean-app") is None
