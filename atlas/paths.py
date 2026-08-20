"""Where Claude Code keeps its state, and which of it we read.

Everything here is read-only. Nothing in this package writes to ~/.claude.
"""

import os
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
