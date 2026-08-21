"""Where Claude Code keeps its state, and which of it we read.

Everything here is read-only. Nothing in this package writes to ~/.claude.
"""

import os
import sys
from pathlib import Path


def claude_home() -> Path:
    """Root of the Claude Code state directory."""
    return Path(os.environ.get("ATLAS_CLAUDE_HOME", Path.home() / ".claude"))


def transcript_files(root: Path | None = None) -> list[Path]:
    """Every session transcript, at any depth.

    ⚠️ Depth matters. Main sessions live at ``projects/<project>/<uuid>.jsonl``
    but subagent transcripts are one level deeper, at
    ``projects/<project>/<session-uuid>/subagents/agent-<id>.jsonl``. A glob of
    ``*/*.jsonl`` silently drops every subagent run — it dropped 4 of 22 files
    (1.0 MB) the first time this was measured by hand. See docs/disproven.md.
    """
    root = root or claude_home()
    projects = root / "projects"
    if not projects.is_dir():
        return []
    return sorted(projects.rglob("*.jsonl"))


def classify(path: Path, root: Path | None = None) -> tuple[str, str, str | None]:
    """Return ``(project, kind, parent_session_id)`` for a transcript path."""
    root = root or claude_home()
    rel = path.relative_to(root / "projects")
    project = rel.parts[0]
    if "subagents" in rel.parts:
        # projects/<project>/<parent-session>/subagents/agent-<id>.jsonl
        return project, "subagent", rel.parts[1]
    return project, "main", None


def enterprise_settings_path() -> Path:
    """Managed policy settings, which no lower scope can override.

    Absent on this machine, which is *not* the same as "no policy applies" —
    see ``config.resolve``. Overridable with ``ATLAS_ENTERPRISE_SETTINGS`` so
    the unreadable case can be tested.
    """
    override = os.environ.get("ATLAS_ENTERPRISE_SETTINGS")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path("/Library/Application Support/ClaudeCode/managed-settings.json")
    if sys.platform.startswith("win"):
        return Path("C:/ProgramData/ClaudeCode/managed-settings.json")
    return Path("/etc/claude-code/managed-settings.json")


def user_config_path(root: Path | None = None) -> Path:
    """``~/.claude.json`` — the sibling file, not the directory.

    Holds per-project state including ``allowedTools``: the "always allow"
    answers accumulated from permission prompts. They are real permission
    grants that appear in no ``settings.json``.
    """
    root = root or claude_home()
    return root.parent / (root.name + ".json")


def encode_project_dir(root: Path) -> str:
    """The ``projects/`` directory name Claude Code uses for a working directory.

    ``/home/sean/dev/ai-atlas`` → ``-home-sean-dev-ai-atlas``.

    ⚠️ Encoding is a function; decoding is not. ``-home-sean-personal-projects``
    could be ``/home/sean/personal-projects`` or ``/home/sean/personal/projects``
    and nothing in the name says which. So we never decode: we take ``cwd`` from
    the transcript, which is ground truth, and confirm it by encoding it back.
    A wrong guess then fails to match and the answer is "unknown" rather than a
    plausible wrong path. The treatment of ``.`` is a guess for that reason —
    no path on this machine has one.
    """
    return str(root).replace("/", "-").replace(".", "-")


def project_root_for(cwd: str, project_dir: str) -> Path | None:
    """The project root a session ran in, or ``None`` if it cannot be confirmed.

    ``cwd`` may be a subdirectory — a session that ran a command in
    ``app/templates/partials`` records that. Walk up until an ancestor encodes
    to the transcript's own directory name.
    """
    here = Path(cwd)
    for candidate in (here, *here.parents):
        if encode_project_dir(candidate) == project_dir:
            return candidate
    return None
