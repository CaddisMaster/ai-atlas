"""Effective configuration, resolved across every scope, with provenance.

⚠️ This module exists because of one specific failure. An analysis read
``~/.claude/settings.json`` — three keys — and reported that the user had no
hooks, no permission rules, no skills and no slash commands. All four claims
were false: a project scope one directory away held all four. Reading one scope
and reporting on all of them is the mistake this code is shaped to prevent.
See docs/decisions/0001 and docs/disproven.md.

Three rules follow from that:

1. **Every fact carries the scope it came from.** There is no way to get an
   item out of here without its source path.
2. **A scope we could not read is ``unknown``, never ``absent``.** An enterprise
   policy we lack permission to read, a settings file with a syntax error, and a
   settings file that does not exist are three different answers.
3. **Every place we looked is recorded**, found or not. "Never configured" is a
   claim about the places checked, so the places checked are evidence and are
   stored alongside the findings.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .paths import claude_home, encode_project_dir, enterprise_settings_path, user_config_path

PRESENT, ABSENT, UNKNOWN = "present", "absent", "unknown"

# Highest precedence first. Enterprise managed policy cannot be overridden by
# anything below it; a project's local settings beat its shared ones; the user's
# settings are the floor.
#
# ``cli`` sits between enterprise and local and is deliberately absent from this
# tuple: flags passed to `claude` are not written to disk, so they are reported
# as an unknown scope rather than resolved. ``dynamic`` is ranked last and its
# position is a guess — it holds accumulated "always allow" answers, which are
# additive to permissions, so its rank has no effect on any answer we give.
PRECEDENCE = ("enterprise", "local", "project", "user", "dynamic")

# Kinds where the highest-precedence scope wins and lower ones are shadowed.
# Everything else accumulates: a project hook does not replace a user hook, and
# a permission rule from any scope applies.
SHADOWING_KINDS = frozenset({"setting", "agent", "command", "skill"})

# Settings values are stored as a hash plus a short preview. The hash is what
# makes a config change detectable between snapshots; the preview keeps the
# database from carrying a copy of everything in settings.json, which
# SECURITY.md notes is itself sensitive.
PREVIEW_CHARS = 200


@dataclass(frozen=True)
class Scope:
    """Somewhere we looked, and what we found there."""

    name: str
    path: str
    state: str
    detail: str = ""


@dataclass(frozen=True)
class Item:
    kind: str          # agent | command | skill | hook | setting | memory | mcp
    name: str
    scope: str
    source_path: str
    detail: str = ""
    value_hash: str = ""
    shadowed: bool = False


@dataclass(frozen=True)
class Rule:
    """One permission rule. ``Bash(git push:*)`` splits into tool and argument."""

    scope: str
    action: str        # allow | deny | ask
    tool: str
    argument: str | None
    pattern: str
    source_path: str


@dataclass
class Resolution:
    project_root: Path | None = None
    project_dir: str | None = None
    scopes: list[Scope] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    def of_kind(self, kind: str, include_shadowed: bool = True) -> list[Item]:
        return [i for i in self.items
                if i.kind == kind and (include_shadowed or not i.shadowed)]

    def scope_state(self, name: str) -> str:
        """Worst-case state for a scope: unknown beats present beats absent."""
        states = {s.state for s in self.scopes if s.name == name}
        for state in (UNKNOWN, PRESENT, ABSENT):
            if state in states:
                return state
        return ABSENT


def _rank(scope: str) -> int:
    return PRECEDENCE.index(scope) if scope in PRECEDENCE else len(PRECEDENCE)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _preview(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "…"


def _read_json(path: Path) -> tuple[dict | None, str, str]:
    """``(data, state, detail)``.

    A file that is missing, unreadable and malformed are three distinct answers.
    Only the first is ``absent``: the other two are things we failed to read,
    and reporting them as "not configured" is how confident false claims get
    made.
    """
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return None, ABSENT, ""
    except (PermissionError, OSError) as exc:
        return None, UNKNOWN, f"unreadable: {exc.__class__.__name__}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, UNKNOWN, f"malformed JSON at line {exc.lineno}"
    if not isinstance(data, dict):
        return None, UNKNOWN, f"expected an object, found {type(data).__name__}"
    return data, PRESENT, ""


def _hook_commands(entries: object) -> list[tuple[str, str]]:
    """``(matcher, command)`` for every hook under one event."""
    out: list[tuple[str, str]] = []
    if not isinstance(entries, list):
        return out
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        matcher = entry.get("matcher") or ""
        for hook in entry.get("hooks") or []:
            if isinstance(hook, dict):
                out.append((matcher, hook.get("command") or hook.get("type") or "?"))
    return out


def split_rule(pattern: str) -> tuple[str, str | None]:
    """``Bash(git push:*)`` → ``("Bash", "git push:*")``; ``WebFetch`` → ``("WebFetch", None)``."""
    text = pattern.strip()
    if text.endswith(")") and "(" in text:
        tool, _, argument = text.partition("(")
        return tool.strip(), argument[:-1]
    return text, None


def _settings_scope(res: Resolution, scope: str, path: Path) -> None:
    data, state, detail = _read_json(path)
    res.scopes.append(Scope(scope, str(path), state, detail))
    if data is None:
        return

    permissions = data.get("permissions") or {}
    if isinstance(permissions, dict):
        for action in ("allow", "deny", "ask"):
            for pattern in permissions.get(action) or []:
                tool, argument = split_rule(str(pattern))
                res.rules.append(Rule(scope, action, tool, argument, str(pattern), str(path)))
        for key, value in permissions.items():
            if key not in ("allow", "deny", "ask"):
                res.items.append(Item("setting", f"permissions.{key}", scope, str(path),
                                      _preview(value), _hash(value)))

    hooks = data.get("hooks") or {}
    if isinstance(hooks, dict):
        for event, entries in hooks.items():
            for matcher, command in _hook_commands(entries):
                name = f"{event}:{matcher}" if matcher else event
                res.items.append(Item("hook", name, scope, str(path),
                                      _preview(command), _hash(command)))

    for key, value in data.items():
        if key in ("permissions", "hooks"):
            continue
        res.items.append(Item("setting", key, scope, str(path), _preview(value), _hash(value)))


def _listdir(res: Resolution, scope: str, path: Path, pattern: str) -> list[Path] | None:
    """Glob a config directory, recording what we found — or that we could not look."""
    if not path.exists():
        res.scopes.append(Scope(scope, str(path), ABSENT))
        return None
    try:
        found = sorted(p for p in path.glob(pattern) if p.is_file())
    except (PermissionError, OSError) as exc:
        res.scopes.append(Scope(scope, str(path), UNKNOWN, f"unreadable: {exc.__class__.__name__}"))
        return None
    res.scopes.append(Scope(scope, str(path), PRESENT, f"{len(found)} file(s)"))
    return found


def _tree_scope(res: Resolution, scope: str, base: Path) -> None:
    """Subagents, slash commands and skills, which are files rather than settings keys."""
    for path in _listdir(res, scope, base / "agents", "**/*.md") or []:
        res.items.append(Item("agent", path.stem, scope, str(path)))

    for path in _listdir(res, scope, base / "commands", "**/*.md") or []:
        rel = path.relative_to(base / "commands").with_suffix("")
        res.items.append(Item("command", "/" + ":".join(rel.parts), scope, str(path)))

    # A skill is a directory holding SKILL.md, so the skill's name is the
    # directory's — never the file's, which is always "SKILL".
    for path in _listdir(res, scope, base / "skills", "*/SKILL.md") or []:
        res.items.append(Item("skill", path.parent.name, scope, str(path)))


def _memory_scope(res: Resolution, scope: str, path: Path) -> None:
    try:
        text = path.read_text()
    except FileNotFoundError:
        res.scopes.append(Scope(scope, str(path), ABSENT))
        return
    except (PermissionError, OSError) as exc:
        res.scopes.append(Scope(scope, str(path), UNKNOWN, f"unreadable: {exc.__class__.__name__}"))
        return
    res.scopes.append(Scope(scope, str(path), PRESENT))
    # The body is not stored: it is prose the user wrote, it can be long, and a
    # hash is all that is needed to see it change between snapshots.
    res.items.append(Item("memory", path.name, scope, str(path),
                          f"{len(text.splitlines())} lines", _hash(text)))


def _mcp_scope(res: Resolution, scope: str, path: Path) -> None:
    data, state, detail = _read_json(path)
    res.scopes.append(Scope(scope, str(path), state, detail))
    if data is None:
        return
    for name, value in (data.get("mcpServers") or {}).items():
        res.items.append(Item("mcp", name, scope, str(path), _preview(value), _hash(value)))


def _dynamic_scope(res: Resolution, root: Path) -> None:
    """``~/.claude.json`` — per-project state, including permissions granted by prompt.

    "Always allow" answers accumulate here rather than in any ``settings.json``.
    A permissions audit that reads only settings files misses every rule the
    user created by pressing a key.
    """
    path = user_config_path(root)
    data, state, detail = _read_json(path)
    res.scopes.append(Scope("dynamic", str(path), state, detail))
    if data is None or not res.project_root:
        return
    entry = (data.get("projects") or {}).get(str(res.project_root))
    if not isinstance(entry, dict):
        return
    for pattern in entry.get("allowedTools") or []:
        tool, argument = split_rule(str(pattern))
        res.rules.append(Rule("dynamic", "allow", tool, argument, str(pattern), str(path)))
    for name, value in (entry.get("mcpServers") or {}).items():
        res.items.append(Item("mcp", name, "dynamic", str(path), _preview(value), _hash(value)))
    if "hasTrustDialogAccepted" in entry:
        value = entry["hasTrustDialogAccepted"]
        res.items.append(Item("setting", "hasTrustDialogAccepted", "dynamic", str(path),
                              _preview(value), _hash(value)))


def _mark_shadowed(res: Resolution) -> None:
    """Within a shadowing kind, the highest-precedence scope wins; the rest are kept."""
    best: dict[tuple[str, str], int] = {}
    for item in res.items:
        if item.kind not in SHADOWING_KINDS:
            continue
        key = (item.kind, item.name)
        best[key] = min(best.get(key, len(PRECEDENCE)), _rank(item.scope))
    res.items = [
        Item(i.kind, i.name, i.scope, i.source_path, i.detail, i.value_hash,
             shadowed=i.kind in SHADOWING_KINDS and _rank(i.scope) > best[(i.kind, i.name)])
        for i in res.items
    ]


def resolve(project_root: Path | str | None = None,
            root: Path | None = None,
            enterprise: Path | None = None) -> Resolution:
    """Resolve configuration for one project across every scope.

    ``project_root`` is the working directory of the project — ``None`` resolves
    the machine-wide scopes only, which is what "what does this user have set up
    at all" means.
    """
    root = root or claude_home()
    res = Resolution(project_root=Path(project_root) if project_root else None)
    if res.project_root:
        res.project_dir = encode_project_dir(res.project_root)

    _settings_scope(res, "enterprise", enterprise or enterprise_settings_path())

    # Flags given to `claude` are not written anywhere we can read. Saying so is
    # the whole point: an unrecorded scope is unknown, and a resolution that
    # quietly assumed it was empty would be the original bug in a new place.
    res.scopes.append(Scope("cli", "", UNKNOWN, "command-line flags are not recorded on disk"))

    if res.project_root:
        claude_dir = res.project_root / ".claude"
        _settings_scope(res, "local", claude_dir / "settings.local.json")
        _settings_scope(res, "project", claude_dir / "settings.json")
        _tree_scope(res, "project", claude_dir)
        _memory_scope(res, "project", res.project_root / "CLAUDE.md")
        _memory_scope(res, "local", res.project_root / "CLAUDE.local.md")
        _mcp_scope(res, "project", res.project_root / ".mcp.json")

    _settings_scope(res, "user", root / "settings.json")
    _tree_scope(res, "user", root)
    _memory_scope(res, "user", root / "CLAUDE.md")
    _dynamic_scope(res, root)

    _mark_shadowed(res)
    return res


def fingerprint(res: Resolution) -> str:
    """Identity of a whole resolution, so an unchanged re-run is not a new snapshot."""
    payload = [
        [[s.name, s.path, s.state, s.detail] for s in res.scopes],
        [[i.kind, i.name, i.scope, i.source_path, i.value_hash, int(i.shadowed)] for i in res.items],
        [[r.scope, r.action, r.pattern, r.source_path] for r in res.rules],
    ]
    return _hash(payload)


def save(conn, res: Resolution) -> tuple[int, bool]:
    """Store a resolution. Returns ``(snap_id, is_new)``.

    Config is kept as history rather than as a current value: a milestone from
    here, "did that change help?" needs the configuration as it stood before the
    change as much as after it. An identical re-run is not a change, so it
    reuses the existing snapshot instead of filling the table with duplicates.
    """
    from . import PARSER_VERSION  # local import keeps the module import-light

    root = str(res.project_root) if res.project_root else None
    fp = fingerprint(res)
    last = conn.execute(
        "SELECT id, fingerprint FROM config_snap WHERE project_root IS ? ORDER BY id DESC LIMIT 1",
        (root,),
    ).fetchone()
    if last and last["fingerprint"] == fp:
        return last["id"], False

    cur = conn.execute(
        "INSERT INTO config_snap (taken, project_root, project_dir, fingerprint, parser_version)"
        " VALUES (?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), root, res.project_dir, fp, PARSER_VERSION),
    )
    snap_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO config_scopes (snap_id, scope, path, state, detail) VALUES (?, ?, ?, ?, ?)",
        [(snap_id, s.name, s.path, s.state, s.detail) for s in res.scopes],
    )
    conn.executemany(
        "INSERT INTO config_items (snap_id, kind, name, scope, source_path, detail, value_hash,"
        " shadowed, parser_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(snap_id, i.kind, i.name, i.scope, i.source_path, i.detail, i.value_hash,
          int(i.shadowed), PARSER_VERSION) for i in res.items],
    )
    conn.executemany(
        "INSERT INTO rules (snap_id, scope, action, tool, argument, pattern, source_path,"
        " parser_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(snap_id, r.scope, r.action, r.tool, r.argument, r.pattern, r.source_path,
          PARSER_VERSION) for r in res.rules],
    )
    conn.commit()
    return snap_id, True
