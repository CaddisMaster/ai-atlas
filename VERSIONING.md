# Versioning

## The scheme

`MAJOR.MINOR.PATCH`, tagged `vX.Y.Z`. The release is the unit, not the feature —
a version number describes a state of the whole application, not the arrival of
one thing.

## Why the numbering starts at 0.1.0

`0.x` means the storage schema is not stable. `atlas.db` may need to be deleted
and rebuilt between releases, and that is an acceptable cost right now because
rebuilding is cheap: the source of truth is `~/.claude`, not the database.

That stops being true at `1.0.0`, which means: **the schema migrates rather than
rebuilds.** Once history exists that cannot be re-derived — measured
interventions, dismissed proposals, human confirmations — deleting the database
throws away real work.

## The parser version is not the release version

`atlas.PARSER_VERSION` is separate and independent. It increments whenever this
code's *interpretation* of a transcript changes, and every parsed row carries
the version that produced it.

The point is to make format drift visible instead of silent. When Anthropic
changes the transcript format, rows on either side of the change are not
comparable — and a longitudinal tool that quietly compares them is worse than no
tool at all.

## Changelog

Every user-visible change gets an entry under `## [Unreleased]` in
[CHANGELOG.md](CHANGELOG.md), in the same commit as the change. The `Stop` hook
in `.claude/hooks/` catches omissions, but it fires at the end of the session —
writing it as you go is cheaper.
