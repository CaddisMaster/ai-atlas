"""What a tool call was, in a form that can repeat.

89% of the tool calls in the corpus are `Bash`, so the tool name is not a unit
of repetition. These tests pin the unit that replaced it — and two of them are
regressions for defects found by running the extractor over 2,780 real calls.
"""

import pytest

from atlas.signature import bash_signature, tool_signature


@pytest.mark.parametrize("command,expected", [
    # ⚠️ A third of real commands are multi-line. Leaving "\n" out of the
    # separators put 48 calls into a bucket called "?" — the `cd` swallowed
    # everything after it.
    ("cd /home/sean/project\nsed -n '60,120p' test.sh", "sed"),
    ("cd app && git log --oneline -8", "git log"),
    # An echo is a label somebody printed before the real command.
    ('echo "=== tests ==="; tmux capture-pane -p -t bb:tests', "tmux capture-pane"),
    ("echo hello", "echo"),                      # unless it is the whole command
    ("for n in 201 202; do\n  gh issue view $n\ndone", "gh issue"),
    ("SP=/tmp/scratch\npython3 script.py", "python3"),
    ("wc -l app/static/style.css", "wc"),        # a path is an argument, not a subcommand
    (".venv/bin/pytest -q", "pytest"),           # the program, not the path to it
    ("./test.sh", "test.sh"),
    ("git commit -m 'fix the thing'", "git commit"),
    ("", "?"),
])
def test_a_command_reduces_to_its_first_two_meaningful_words(command, expected):
    assert bash_signature(command) == expected


def test_a_command_line_does_not_survive_into_the_database():
    """The signature forgets on purpose.

    A command line carries paths, hostnames and occasionally a secret somebody
    pasted into a shell. Keeping two words means the database learns that you
    commit often and never learns what you committed.
    """
    signature = tool_signature("Bash", {
        "command": "git commit -m 'deploy with ANTHROPIC_API_KEY=sk-ant-secret'"})
    assert signature == "Bash:git commit"
    assert "sk-ant" not in signature


@pytest.mark.parametrize("name,tool_input,expected", [
    ("Read", {"file_path": "/home/sean/app/models.py"}, "Read:.py"),
    ("Edit", {"file_path": "docs/status.md"}, "Edit:.md"),
    ("Write", {"file_path": "/etc/hosts"}, "Write:no-extension"),
    ("Skill", {"skill": "verify", "args": "the whole PR"}, "Skill:verify"),
    ("Task", {"subagent_type": "Explore"}, "Task:Explore"),
    ("Grep", {"pattern": "TODO", "path": "app/"}, "Grep"),
    ("Bash", None, "Bash"),
    ("SomethingNew", {"whatever": 1}, "SomethingNew"),
])
def test_a_tool_signature_generalises_its_input(name, tool_input, expected):
    assert tool_signature(name, tool_input) == expected
