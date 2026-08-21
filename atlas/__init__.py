"""ai-atlas — a measurement system for how you work with Claude Code."""

__version__ = "0.1.0"

# Bumped whenever the parser's interpretation of a transcript changes. Every row
# carries the version that produced it, so a schema change on Anthropic's side
# leaves a visible seam rather than silently poisoning comparisons.
# v2 — sessions carry the working directory they ran in, taken from each
# record's `cwd`. It is how a transcript is tied to the project configuration
# that produced it; the directory name under projects/ cannot be decoded back
# into a path. See paths.encode_project_dir.
PARSER_VERSION = 2
