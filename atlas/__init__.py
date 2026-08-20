"""ai-atlas — a measurement system for how you work with Claude Code."""

__version__ = "0.1.0"

# Bumped whenever the parser's interpretation of a transcript changes. Every row
# carries the version that produced it, so a schema change on Anthropic's side
# leaves a visible seam rather than silently poisoning comparisons.
PARSER_VERSION = 1
