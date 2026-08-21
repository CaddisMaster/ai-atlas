"""Apply acceptance tests.

This is the only module that writes anything, so these tests are mostly about
what it refuses to do. The failure being guarded against is a tool that edits
somebody's Claude Code configuration in a way they did not follow — and the
worst version of that is not a crash, it is a diff so noisy that nobody reads
it.
"""

import json

import pytest

from atlas.apply import Refused, add_command, add_hook, add_rule, backups_dir, guard, write
from atlas.paths import claude_home

SETTINGS = {
    "model": "opus",
    # ⚠️ Real settings files are full of these. See test_prose_survives_the_edit.
    "note": "kept — because it was written by a person",
    "permissions": {"allow": ["Bash(./test.sh)"], "deny": ["Bash(git push --force*)"]},
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "./guard.sh"}]}]},
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A project, a fake ~/.claude, and a database that is not the real one."""
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "atlas.db"))
    monkeypatch.setenv("ATLAS_CLAUDE_HOME", str(tmp_path / ".claude"))
    project = tmp_path / "work" / "demo-app"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "settings.json").write_text(json.dumps(SETTINGS, indent=2) + "\n")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "settings.json").write_text('{"theme": "dark"}\n')
    return project


def _settings(project):
    return json.loads((project / ".claude" / "settings.json").read_text())


def test_project_scope_refuses_to_write_inside_claude_home(workspace):
    """`~/.claude` is somebody's irreplaceable history. Being pointed at it is a
    refusal, not a prompt."""
    with pytest.raises(Refused, match="read-only"):
        add_rule(claude_home(), "Bash(rg:*)")


def test_user_scope_may_write_exactly_one_file(workspace):
    """Opt-in, and then only settings.json — transcripts, history and plugin
    state stay untouchable however the flags are combined."""
    change = add_rule(None, "Bash(rg:*)", scope="user")
    assert change.path == claude_home() / "settings.json"

    # The guard is what protects this, so it is what gets tested: no path under
    # ~/.claude other than settings.json is writable, whatever asks.
    for forbidden in ("projects/session.jsonl", "history.jsonl", "settings.local.json"):
        with pytest.raises(Refused, match="and nothing else"):
            guard(claude_home() / forbidden, "user", None)


def test_a_symlink_out_of_the_project_is_refused(workspace):
    """A settings.json that is a symlink into ~/.claude passes every check made
    on the path as written. So the check is made on the resolved path."""
    settings = workspace / ".claude" / "settings.json"
    settings.unlink()
    settings.symlink_to(claude_home() / "settings.json")

    with pytest.raises(Refused, match="read-only"):
        add_rule(workspace, "Bash(rg:*)")


def test_a_malformed_settings_file_is_never_rewritten(workspace):
    """Rewriting a file we could not parse would silently discard whatever the
    broken part was."""
    (workspace / ".claude" / "settings.json").write_text("{ oops")
    with pytest.raises(Refused, match="not valid JSON"):
        add_rule(workspace, "Bash(rg:*)")


def test_building_a_change_writes_nothing(workspace):
    """Refusing is the default: the diff is produced without touching the disk."""
    before = (workspace / ".claude" / "settings.json").read_text()
    change = add_rule(workspace, "Bash(rg:*)")

    assert "Bash(rg:*)" in change.diff
    assert (workspace / ".claude" / "settings.json").read_text() == before


def test_prose_survives_the_edit(workspace):
    """The em-dash regression.

    `json.dumps` escapes non-ASCII by default, so adding one permission rule to
    the real settings file rewrote every em dash in it as `\\u2014` — a
    thirty-line diff through prose the user had written. A tool that edits
    configuration cannot do that and be trusted with it again.
    """
    conn_settings = workspace / ".claude" / "settings.json"
    change = add_rule(workspace, "Bash(rg:*)")

    assert "\\u2014" not in change.after
    assert "written by a person" in change.after
    added = [line for line in change.diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert len(added) <= 3, f"one rule should be a small diff, got {added}"
    assert conn_settings.read_text() == change.before


def test_an_existing_rule_is_a_no_op(conn, workspace):
    change = add_rule(workspace, "Bash(./test.sh)")
    assert change.already
    assert change.diff == ""
    assert write(conn, change) == (None, None)


def test_everything_else_in_the_file_survives(conn, workspace):
    change = add_rule(workspace, "Bash(rg:*)")
    write(conn, change)

    data = _settings(workspace)
    assert data["model"] == "opus"
    assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == "./guard.sh"
    assert data["permissions"]["deny"] == ["Bash(git push --force*)"]
    assert data["permissions"]["allow"] == ["Bash(./test.sh)", "Bash(rg:*)"]


def test_a_backup_lands_outside_claude_home(conn, workspace):
    backup, _ = write(conn, add_rule(workspace, "Bash(rg:*)"))
    assert backup is not None and backup.exists()
    assert claude_home() not in backup.parents, "restoring must not depend on writing there"
    assert json.loads(backup.read_text())["permissions"]["allow"] == ["Bash(./test.sh)"]


def test_the_write_leaves_no_temporary_file(conn, workspace):
    """Renamed into place, so an interrupted write cannot leave half a settings
    file behind."""
    write(conn, add_rule(workspace, "Bash(rg:*)"))
    assert list((workspace / ".claude").glob("*.atlas-tmp")) == []
    assert _settings(workspace)["permissions"]["allow"][-1] == "Bash(rg:*)"


def test_applying_records_a_dated_intervention(conn, workspace):
    """The loop closes here: a change made through this tool is measurable by
    it afterwards, because applying it wrote down the date."""
    _, intervention_id = write(conn, add_rule(workspace, "Bash(rg:*)"))
    row = conn.execute("SELECT * FROM interventions WHERE id = ?", (intervention_id,)).fetchone()
    assert row["source"] == "apply"
    assert "Bash(rg:*)" in row["what"]
    assert row["happened"] and row["project_root"] == str(workspace)


def test_a_hook_is_not_added_twice(conn, workspace):
    assert add_hook(workspace, "Stop", "./guard.sh").already
    change = add_hook(workspace, "Stop", "./other.sh")
    write(conn, change)
    commands = [h["command"] for entry in _settings(workspace)["hooks"]["Stop"]
                for h in entry["hooks"]]
    assert commands == ["./guard.sh", "./other.sh"]


def test_a_command_stub_is_written_as_unfinished(conn, workspace):
    """Detection is deterministic; the artifact is the human's.

    What repeats is in the transcripts. Why it repeats, and what to do when step
    three fails, is not — so the stub records the evidence and leaves a TODO
    where the judgement goes.
    """
    change = add_command(workspace, "ship", ["Bash:git add", "Bash:git push"],
                         occurrences=4, sessions=3)
    write(conn, change)

    body = (workspace / ".claude" / "commands" / "ship.md").read_text()
    assert "TODO" in body
    assert "4 occurrences across 3 sessions" in body
    assert "Bash:git push" in body
    assert "not a working command" in body


def test_a_command_name_that_is_not_a_name_is_refused(workspace):
    with pytest.raises(Refused, match="usable command name"):
        add_command(workspace, "../../etc/passwd", ["Bash:ls"])


def test_the_backups_directory_is_beside_the_database(workspace):
    assert backups_dir().name == "backups"
    assert claude_home() not in backups_dir().parents
