"""Write a proposal into a settings file — after showing exactly what changes.

⚠️ This is the only module in the project that writes anywhere, and it is
written against its own worst case: a tool that edits somebody's Claude Code
configuration without them fully understanding what it did.

Non-negotiable 1 says `~/.claude` is read-only, and `~/.claude/settings.json`
lives inside it. The tension is resolved by narrowing rather than by exception:

- **Project scope is the default and needs no flag.** It writes
  `<project>/.claude/…`, which is outside `~/.claude` entirely and is usually
  in the project's own git history, where a mistake is one `git checkout` away.
- **User scope is opt-in per invocation**, and then exactly one file is
  writable: `~/.claude/settings.json`. Everything else under `~/.claude` —
  transcripts, history, file-history, plugin state — stays read-only, always.
  It is somebody's irreplaceable record and this tool has no business in it.
- **Refusing is the default.** Without `--yes` the diff is printed and nothing
  is written.
- **A backup is kept outside `~/.claude`**, in ai-atlas's own data directory,
  so restoring never depends on us having written into the source of truth.

Applying also records an intervention with today's date, which is the point of
the whole exercise: a change you make through this tool is measurable by it
afterwards.
"""

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path

from .db import default_path
from .interventions import record
from .paths import claude_home

INDENT = 2

# Filenames under a project's .claude/ this may touch. Anything else is a
# refusal rather than a question.
PROJECT_SETTINGS = "settings.json"
USER_SETTINGS = "settings.json"


class Refused(Exception):
    """A write this tool will not perform, whatever flags it was given."""


@dataclass
class Change:
    path: Path
    scope: str
    kind: str            # rule | hook | command
    what: str
    before: str
    after: str
    already: bool = False

    @property
    def diff(self) -> str:
        return "".join(unified_diff(
            self.before.splitlines(keepends=True), self.after.splitlines(keepends=True),
            fromfile=f"{self.path} (now)", tofile=f"{self.path} (after)"))


def backups_dir() -> Path:
    """Beside the database, never inside ~/.claude.

    Restoring a settings file must not depend on this tool having written into
    the directory it promises not to write into.
    """
    return default_path().parent / "backups"


def target(project_root: Path | str | None, scope: str, root: Path | None = None) -> Path:
    root = root or claude_home()
    if scope == "user":
        return root / USER_SETTINGS
    if not project_root:
        raise Refused("project scope needs a project directory")
    return Path(project_root) / ".claude" / PROJECT_SETTINGS


def guard(path: Path, scope: str, project_root: Path | str | None,
          root: Path | None = None) -> Path:
    """Refuse anything outside the two places this tool may write.

    ⚠️ Resolved before checking. A `.claude/settings.json` that is a symlink
    into `~/.claude/projects` would otherwise pass a check on the path as
    written and land in a transcript directory.
    """
    root = (root or claude_home()).resolve()
    resolved = path.resolve()

    inside_claude = resolved == root or root in resolved.parents
    if scope == "user":
        if resolved != (root / USER_SETTINGS).resolve():
            raise Refused(f"user scope may write {root / USER_SETTINGS} and nothing else; "
                          f"refusing {resolved}")
        return resolved

    if inside_claude:
        raise Refused(f"{resolved} is inside {root}, which is read-only — "
                      "pass --scope user if you meant the user settings file")
    if project_root:
        base = Path(project_root).resolve()
        if base != resolved and base not in resolved.parents:
            raise Refused(f"{resolved} is outside the project {base}")
    if resolved.name != PROJECT_SETTINGS:
        raise Refused(f"project scope may write {PROJECT_SETTINGS}; refusing {resolved.name}")
    return resolved


def _load(path: Path) -> tuple[dict, str]:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}, ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Refused(f"{path} is not valid JSON ({exc.msg} at line {exc.lineno}) — "
                      "fix it by hand rather than letting this tool rewrite it") from exc
    if not isinstance(data, dict):
        raise Refused(f"{path} does not contain an object")
    return data, text


def _render(data: dict) -> str:
    """⚠️ ``ensure_ascii=False``, or every em dash in the file becomes ``\\u2014``.

    The real `~/.claude/settings.json` on this machine is full of them. With the
    default, adding one permission rule produced a thirty-line diff that
    rewrote prose the user had written — which is exactly how a tool that edits
    configuration earns a reputation for mangling it.
    """
    return json.dumps(data, indent=INDENT, ensure_ascii=False) + "\n"


def add_rule(project_root, pattern: str, *, action: str = "allow", scope: str = "project",
             root: Path | None = None) -> Change:
    if action not in ("allow", "deny", "ask"):
        raise Refused(f"unknown permission action {action!r}")
    path = guard(target(project_root, scope, root), scope, project_root, root)
    data, before = _load(path)

    permissions = data.setdefault("permissions", {})
    rules = permissions.setdefault(action, [])
    already = pattern in rules
    if not already:
        rules.append(pattern)
    return Change(path, scope, "rule", f"{action} {pattern}", before,
                  before if already else _render(data), already)


def add_hook(project_root, event: str, command: str, *, matcher: str = "",
             scope: str = "project", root: Path | None = None) -> Change:
    path = guard(target(project_root, scope, root), scope, project_root, root)
    data, before = _load(path)

    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault(event, [])
    already = any(h.get("command") == command
                  for entry in entries if isinstance(entry, dict)
                  for h in entry.get("hooks") or [])
    if not already:
        entry: dict = {"hooks": [{"type": "command", "command": command}]}
        if matcher:
            entry["matcher"] = matcher
        entries.append(entry)
    return Change(path, scope, "hook", f"{event} → {command}", before,
                  before if already else _render(data), already)


COMMAND_TEMPLATE = """---
description: {description}
---

<!-- Drafted by ai-atlas from {occurrences} occurrences across {sessions} sessions.
     The sequence below is what was *observed*. It is not a working command
     until you have said what it is for and what should happen when a step
     fails — that part is not in any transcript. -->

## Observed sequence

{steps}

## What this should actually do

TODO — write this before relying on it.
"""


def add_command(project_root, name: str, sequence: list[str], *, occurrences: int = 0,
                sessions: int = 0, description: str = "") -> Change:
    """Write a slash command **stub**, never a finished command.

    Detection is deterministic and the artifact is the human's (CLAUDE.md,
    non-negotiable 3). What repeats is in the transcripts; why it repeats, and
    what to do when step three fails, is not. So this writes down the evidence
    and leaves a TODO where the judgement goes.
    """
    if not project_root:
        raise Refused("a slash command is written into a project, so it needs one")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise Refused(f"{name!r} is not a usable command name")

    path = (Path(project_root) / ".claude" / "commands" / f"{name}.md").resolve()
    base = Path(project_root).resolve()
    if base not in path.parents:
        raise Refused(f"{path} is outside the project {base}")
    root = claude_home().resolve()
    if root in path.parents:
        raise Refused(f"{path} is inside {root}, which is read-only")

    before = path.read_text() if path.exists() else ""
    steps = "\n".join(f"{i}. `{step}`" for i, step in enumerate(sequence, start=1))
    after = COMMAND_TEMPLATE.format(
        description=description or f"observed {occurrences} times in {sessions} sessions",
        occurrences=occurrences, sessions=sessions, steps=steps)
    return Change(path, "project", "command", f"/{name}", before, after, before == after)


def write(conn, change: Change, *, note_intervention: bool = True) -> tuple[Path | None, int | None]:
    """Perform the change. Returns ``(backup_path, intervention_id)``.

    Atomic: the new content goes to a temporary file in the same directory and
    is renamed over the target, so an interrupted write cannot leave a
    half-written settings file behind.
    """
    if change.already:
        return None, None

    backup = None
    if change.before:
        backups_dir().mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        backup = backups_dir() / f"{stamp}-{change.path.name}"
        shutil.copy2(change.path, backup)

    change.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = change.path.with_suffix(change.path.suffix + ".atlas-tmp")
    temporary.write_text(change.after)
    os.replace(temporary, change.path)

    intervention_id = None
    if note_intervention:
        # The loop closes here: a change made through this tool is dated, so
        # milestone 6 can measure it later — if enough sessions accumulate.
        intervention_id = record(
            conn, str(Path(change.path).parent.parent) if change.scope == "project" else None,
            f"applied: {change.what}", datetime.now(UTC).isoformat(),
            kind={"rule": "rule", "hook": "hook", "command": "command"}[change.kind],
            source="apply", evidence=f"{change.path} (backup: {backup or 'none — new file'})")
    return backup, intervention_id
