"""What a tool call *was*, in a form that can repeat.

⚠️ This is the milestone-5 problem in one file. 89% of the tool calls in the
corpus this was written against are `Bash`, so a sequence detector that works on
tool names finds `Bash → Bash → Bash` and nothing else. The unit of repetition
has to carry more than the name, and choosing it is most of the work.

The signature is deliberately **lossy**, and that is a feature twice over:

- It generalises. `Bash:git commit` matches every commit, not one message.
- It forgets. A command line contains paths, hostnames, and sometimes a secret
  that was pasted into a shell. Keeping the first two words means the database
  learns that you commit a lot, and never learns what you committed.

Frozen under ``PARSER_VERSION`` — these strings are stored on every tool call,
and changing how they are derived makes old rows incomparable with new ones.
"""

from pathlib import PurePosixPath

# Scaffolding: words that appear where the program name goes but do not name
# the work being done. `cd app && pytest` is a pytest call. `echo "=== tests
# ===" ; tmux capture-pane` is a tmux call with a label in front of it. A loop
# header is a loop header. All of them are skipped in favour of the first real
# program in the command — and if there is nothing else, the scaffolding word is
# the answer, because `echo hi` really is an echo.
SCAFFOLDING = {
    "cd", "export", "source", ".", "sudo", "time", "env", "exec", "echo", "printf",
    "for", "while", "until", "if", "do", "done", "then", "else", "elif", "fi",
    "case", "esac", "function", "{", "(", "[[",
}

# ⚠️ Newlines separate commands as surely as `&&` does, and a third of the
# commands in the corpus are multi-line — `cd /path\nsed -n '60,120p' test.sh`.
# Leaving `\n` out of this tuple put 48 calls into a bucket called `?`.
SEPARATORS = ("&&", "||", ";", "|", "\n")

MAX_TOKEN = 24

# Tools whose signature is the file they touched, generalised to its extension.
BY_EXTENSION = {"Read", "Edit", "Write", "NotebookEdit"}
# Tools naming a thing that is worth keeping whole.
BY_FIELD = {"Skill": "skill", "Agent": "subagent_type", "Task": "subagent_type",
            "SlashCommand": "command"}


def _segments(command: str) -> list[str]:
    parts = [command]
    for sep in SEPARATORS:
        parts = [piece for part in parts for piece in part.split(sep)]
    return [p.strip() for p in parts if p.strip()]


def _looks_like_a_subcommand(token: str) -> bool:
    """`git log` keeps its second word; `wc -l file.css` does not.

    A subcommand is a bare word. Anything carrying a path, a flag, a variable or
    a wildcard is an argument, and arguments are the part we deliberately forget.
    """
    if not token or token.startswith("-"):
        return False
    return all(c.isalnum() or c in "-_" for c in token)


def _name_of(segment: str) -> str | None:
    tokens = segment.split()
    if not tokens:
        return None
    head = tokens[0]
    if "=" in head:                       # SP=/tmp/... — an assignment, not a program
        return None
    program = PurePosixPath(head).name[:MAX_TOKEN]
    if len(tokens) > 1 and _looks_like_a_subcommand(tokens[1]):
        return f"{program} {tokens[1][:MAX_TOKEN]}"
    return program


def bash_signature(command: str) -> str:
    """The first two meaningful words of a shell command.

    `cd app && git log --oneline -8`  → `git log`
    `wc -l app/static/style.css`      → `wc`
    `.venv/bin/pytest -q`             → `pytest`
    `echo "== x"; tmux capture-pane`  → `tmux capture-pane`
    """
    fallback = None
    for segment in _segments(command):
        name = _name_of(segment)
        if name is None:
            continue
        if name.split()[0] in SCAFFOLDING:
            # Named only because there was nothing else in the command, so keep
            # it coarse: `echo hello` and `echo goodbye` are both `echo`.
            fallback = fallback or name.split()[0]
            continue
        return name
    return fallback or "?"


def tool_signature(name: str, tool_input: object) -> str:
    """``Bash:git commit``, ``Edit:.py``, ``Skill:verify``, or just the tool name."""
    if not isinstance(tool_input, dict):
        return name

    if name == "Bash":
        command = tool_input.get("command")
        return f"Bash:{bash_signature(command)}" if isinstance(command, str) else "Bash"

    if name in BY_EXTENSION:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if isinstance(path, str) and path:
            suffix = PurePosixPath(path).suffix
            return f"{name}:{suffix or 'no-extension'}"
        return name

    field = BY_FIELD.get(name)
    if field:
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            return f"{name}:{value.split()[0][:MAX_TOKEN]}"
    return name
