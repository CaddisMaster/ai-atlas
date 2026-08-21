"""Command line entry point: ``python -m atlas <command>``."""

import argparse
import json
import sys
from pathlib import Path

from . import PARSER_VERSION, __version__
from .baseline import ESTABLISHED, FLOOR
from .baseline import build as baseline_build
from .baseline import save as baseline_save
from .config import UNKNOWN, resolve, save
from .db import connect
from .handoff import STALE
from .handoff import run as handoff_run
from .handoff import save as handoff_save
from .ingest import ingest
from .paths import claude_home


def cmd_ingest(args) -> int:
    conn = connect(args.db)
    res = ingest(conn)
    print(f"scanned  {res.files_seen} transcript files under {claude_home()/'projects'}")
    print(f"read     {res.files_read} with new content ({res.bytes_read:,} bytes)")
    print(f"stored   {res.messages:,} messages · {res.tool_calls:,} tool calls · {res.sessions} sessions")
    if res.unknown_types:
        print(f"⚠️  unmodelled record types: {', '.join(sorted(res.unknown_types))}")
    return 0


def cmd_stats(args) -> int:
    conn = connect(args.db)
    q = lambda sql: conn.execute(sql).fetchall()  # noqa: E731

    kinds = q("SELECT kind, COUNT(*) AS n FROM sessions GROUP BY kind ORDER BY n DESC")
    print("sessions by kind")
    for r in kinds:
        print(f"  {r['kind']:<10}{r['n']:>5}")

    print("\nsessions by project")
    for r in q("SELECT project, COUNT(*) AS n FROM sessions GROUP BY project ORDER BY n DESC"):
        print(f"  {r['project'][:52]:<54}{r['n']:>4}")

    print("\ntool calls")
    for r in q("SELECT name, COUNT(*) AS n FROM tool_calls GROUP BY name ORDER BY n DESC"):
        print(f"  {r['name']:<18}{r['n']:>6}")

    tok = q("""SELECT COALESCE(SUM(input),0) i, COALESCE(SUM(output),0) o,
                      COALESCE(SUM(cache_read),0) cr, COALESCE(SUM(cache_creation),0) cc
               FROM usage""")[0]
    total_in = tok["i"] + tok["cr"] + tok["cc"]
    print("\ntokens")
    print(f"  output       {tok['o']:>16,}")
    print(f"  cache read   {tok['cr']:>16,}")
    print(f"  cache create {tok['cc']:>16,}")
    print(f"  fresh input  {tok['i']:>16,}")
    if total_in:
        print(f"  cache hit rate {100 * tok['cr'] / total_in:>13.1f}%")

    unknown = q("SELECT type, count FROM record_types WHERE known = 0 ORDER BY count DESC")
    if unknown:
        print("\n⚠️  unmodelled record types (format drift shows up here)")
        for r in unknown:
            print(f"  {r['type']:<26}{r['count']:>6}")
    return 0


# Kinds in the order a person asks about them, with the heading each gets.
KINDS = [
    ("agent", "subagents"),
    ("command", "slash commands"),
    ("skill", "skills"),
    ("hook", "hooks"),
    ("mcp", "mcp servers"),
    ("memory", "memory files"),
    ("setting", "settings"),
]


def _target(conn, given: str | None) -> Path | None:
    """Which project to resolve for: a path, a known project, or the cwd."""
    if given is None:
        return Path.cwd()
    path = Path(given).expanduser()
    if path.is_dir():
        return path.resolve()
    rows = conn.execute(
        "SELECT DISTINCT project_root FROM sessions WHERE project_root IS NOT NULL"
        " AND project_root LIKE ? ORDER BY project_root",
        (f"%{given}%",),
    ).fetchall()
    if len(rows) == 1:
        return Path(rows[0]["project_root"])
    if not rows:
        print(f"no ingested project matches {given!r}; pass a directory instead", file=sys.stderr)
    else:
        print(f"{given!r} matches {len(rows)} projects:", file=sys.stderr)
        for r in rows:
            print(f"  {r['project_root']}", file=sys.stderr)
    return None


def _print_resolution(res, verbose: bool) -> None:
    print(f"project  {res.project_root or '(machine-wide scopes only)'}")

    print("\nscopes — every place looked, found or not")
    for s in res.scopes:
        note = f"  {s.detail}" if s.detail else ""
        print(f"  {s.name:<11}{s.state:<9}{s.path or '—'}{note}")

    for kind, heading in KINDS:
        items = res.of_kind(kind)
        if not items and not verbose:
            continue
        print(f"\n{heading} ({len([i for i in items if not i.shadowed])})")
        for i in sorted(items, key=lambda i: (i.name, i.scope)):
            flag = "  ← shadowed" if i.shadowed else ""
            detail = f"  {i.detail}" if i.detail and kind != "setting" else ""
            print(f"  {i.name:<28}{i.scope:<11}{i.source_path}{detail}{flag}")

    counts: dict[tuple[str, str], int] = {}
    for r in res.rules:
        counts[(r.scope, r.action)] = counts.get((r.scope, r.action), 0) + 1
    print(f"\npermission rules ({len(res.rules)})")
    for (scope, action), n in sorted(counts.items()):
        print(f"  {action:<8}{n:>4}  {scope}")
    if not res.rules:
        print("  none in any readable scope")

    unknown = [s for s in res.scopes if s.state == UNKNOWN]
    if unknown:
        print("\n⚠️  unknown, which is not the same as absent")
        for s in unknown:
            print(f"  {s.name:<11}{s.path or '—'}  {s.detail}")


def cmd_config(args) -> int:
    conn = connect(args.db)

    if args.all:
        roots = [r["project_root"] for r in conn.execute(
            "SELECT DISTINCT project_root FROM sessions WHERE project_root IS NOT NULL"
            " ORDER BY project_root")]
        if not roots:
            print("no project roots known — run `atlas ingest` first", file=sys.stderr)
            return 1
        for root in roots:
            res = resolve(root)
            if not args.no_save:
                save(conn, res)
            configured = [f"{len(res.of_kind(k, include_shadowed=False))} {h}"
                          for k, h in KINDS if res.of_kind(k, include_shadowed=False)]
            print(f"{root}\n  {len(res.rules)} permission rules · " + " · ".join(configured))
        rootless = conn.execute(
            "SELECT COUNT(*) n FROM sessions WHERE project_root IS NULL").fetchone()["n"]
        if rootless:
            print(f"\n⚠️  {rootless} session(s) with no confirmed project root — "
                  "their working directory could not be reconciled with the transcript path")
        return 0

    target = _target(conn, args.project)
    if target is None:
        return 1
    res = resolve(target)

    if args.json:
        print(json.dumps({
            "project_root": str(res.project_root) if res.project_root else None,
            "scopes": [vars(s) for s in res.scopes],
            "items": [vars(i) for i in res.items],
            "rules": [vars(r) for r in res.rules],
        }, indent=2))
    else:
        _print_resolution(res, args.verbose)

    if not args.no_save:
        snap_id, is_new = save(conn, res)
        if not args.json:
            print(f"\nsnapshot {snap_id}" + ("" if is_new else " (unchanged, reused)"))
    return 0


def cmd_handoff(args) -> int:
    """What the status document claims, and what the repository says."""
    report = handoff_run(args.repo or Path.cwd(), status=args.status, github=args.github)

    if args.json:
        print(json.dumps({
            "repo": str(report.repo),
            "status_path": str(report.status_path) if report.status_path else None,
            "head": report.head,
            "findings": [vars(f) for f in report.findings],
        }, indent=2))
    else:
        print(f"repo     {report.repo}")
        print(f"status   {report.status_path or '—'}")
        shown = report.findings if args.all else [
            f for f in report.findings if f.state != "ok"]
        if not shown:
            print(f"\n✅ nothing contradicts the status document ({len(report.findings)} checks)")
        for f in sorted(shown, key=lambda f: (f.state != STALE, f.check)):
            mark = "⚠️ " if f.state == STALE else ("· " if f.state == "ok" else "?  ")
            print(f"\n{mark}{f.check}  {f.subject}")
            print(f"     claims  {f.claim}")
            print(f"     reality {f.actual}")
            if f.source:
                print(f"     at      {f.source}")
        if not args.github:
            print("\nnot checked: open pull requests and issues "
                  "(pass --github; it is the one call that leaves the machine)")

    if not args.no_save:
        conn = connect(args.db)
        snap_id, is_new = handoff_save(conn, report)
        if not args.json:
            print(f"\nrun {snap_id}" + ("" if is_new else " (unchanged since the last run)"))

    return 1 if (args.strict and report.stale) else 0


def _fmt(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".") if value < 10 else f"{value:.1f}"


def _print_baseline(base) -> None:
    print(f"project     {base.project_root or '(all projects)'}")
    print(f"sessions    {base.n} counted · {len(base.excluded)} excluded")

    if not base.states_a_norm:
        print(f"confidence  unknown — {base.n} session(s) is not a sample "
              f"(a norm needs {FLOOR}). No normal band is stated.")
    else:
        room = "" if base.n >= ESTABLISHED else f", under {ESTABLISHED} — treat as indicative"
        print(f"confidence  {base.confidence} (n = {base.n}{room})")

    shares = [s for s in base.summaries if s.metric.startswith("share_")]
    plain = [s for s in base.summaries if not s.metric.startswith("share_")]

    print(f"\n{'metric':<18}{'median':>10}{'middle half':>22}{'normal band':>20}{'n':>5}")
    for s in plain:
        half = f"{_fmt(s.p25)} – {_fmt(s.p75)}"
        band = f"{_fmt(s.low)} – {_fmt(s.high)}" if base.states_a_norm else "—"
        print(f"{s.metric:<18}{_fmt(s.median):>10}{half:>22}{band:>20}{s.n:>5}")

    if shares:
        print("\ntool mix — share of a session's own tool calls")
        for s in shares:
            half = f"{_fmt(s.p25)} – {_fmt(s.p75)}"
            print(f"  {s.metric[len('share_'):]:<16}{_fmt(s.median):>10}{half:>22}")

    if base.states_a_norm:
        print(f"\nunusual sessions ({len({o.session_id for o in base.outliers})})")
        if not base.outliers:
            widest = max((s for s in plain if s.spread), key=lambda s: s.spread, default=None)
            if widest:
                print("  none — which says as much about the sample as about the sessions:")
                print(f"  the middle half of {widest.metric} already spans "
                      f"{widest.spread:.0f}×, so the band catches almost anything.")
            else:
                print("  none")
        for o in sorted(base.outliers, key=lambda o: o.session_id):
            print(f"  {o.session_id[:8]}  {o.metric} {_fmt(o.value)} "
                  f"({o.direction}; band {_fmt(o.band[0])} – {_fmt(o.band[1])})")

    if base.excluded:
        print(f"\nexcluded ({len(base.excluded)}) — recorded, never dropped")
        for session_id, reason in base.excluded:
            print(f"  {session_id[:8]}  {reason}")


def cmd_baseline(args) -> int:
    conn = connect(args.db)

    if args.all:
        roots = [r["project_root"] for r in conn.execute(
            "SELECT DISTINCT project_root FROM sessions WHERE project_root IS NOT NULL"
            " ORDER BY project_root")]
        if not roots:
            print("no sessions ingested — run `atlas ingest` first", file=sys.stderr)
            return 1
        for root in roots:
            base = baseline_build(conn, root, kind=args.kind)
            if not args.no_save:
                baseline_save(conn, base)
            note = (f"{base.confidence}" if base.states_a_norm
                    else f"unknown — {base.n} session(s), a norm needs {FLOOR}")
            print(f"{root}\n  {base.n} counted · {len(base.excluded)} excluded · {note}")
        return 0

    target = _target(conn, args.project)
    if target is None:
        return 1
    base = baseline_build(conn, str(target), kind=args.kind)
    if not base.counted and not base.excluded:
        print(f"no {args.kind} sessions ingested for {target}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "project_root": base.project_root, "kind": base.kind,
            "n": base.n, "confidence": base.confidence,
            "excluded": base.excluded,
            "summaries": [vars(s) for s in base.summaries],
            "outliers": [{**vars(o), "band": list(o.band)} for o in base.outliers],
            "sessions": base.values,
        }, indent=2))
    else:
        _print_baseline(base)

    if not args.no_save:
        baseline_id, is_new = baseline_save(conn, base)
        if not args.json:
            print(f"\nbaseline {baseline_id}" + ("" if is_new else " (unchanged, reused)"))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atlas", description="Measure how you work with Claude Code.")
    p.add_argument("--version", action="version", version=f"ai-atlas {__version__} (parser v{PARSER_VERSION})")
    p.add_argument("--db", default=None, help="database path (default: ~/.local/share/ai-atlas/atlas.db)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="read new transcript content into the database").set_defaults(fn=cmd_ingest)
    sub.add_parser("stats", help="summarise what has been ingested").set_defaults(fn=cmd_stats)

    cfg = sub.add_parser("config", help="resolve configuration across every scope, with provenance")
    cfg.add_argument("project", nargs="?", help="project directory, or part of a known project path")
    cfg.add_argument("--all", action="store_true", help="every project seen in the transcripts")
    cfg.add_argument("--json", action="store_true", help="full resolution as JSON")
    cfg.add_argument("--verbose", action="store_true", help="show kinds with nothing configured")
    cfg.add_argument("--no-save", action="store_true", help="do not store a snapshot")
    cfg.set_defaults(fn=cmd_config)

    ho = sub.add_parser("handoff", help="check the status document against the repository")
    ho.add_argument("repo", nargs="?", type=Path, help="repository (default: cwd)")
    ho.add_argument("--status", type=Path, help="status document (default: docs/status.md)")
    ho.add_argument("--github", action="store_true",
                    help="also check open PRs — the only network call in ai-atlas")
    ho.add_argument("--all", action="store_true", help="show checks that passed too")
    ho.add_argument("--json", action="store_true", help="findings as JSON")
    ho.add_argument("--strict", action="store_true", help="exit 1 when anything is stale")
    ho.add_argument("--no-save", action="store_true", help="do not store the run")
    ho.set_defaults(fn=cmd_handoff)

    bl = sub.add_parser("baseline", help="what a normal session looks like in one project")
    bl.add_argument("project", nargs="?", help="project directory, or part of a known project path")
    bl.add_argument("--kind", default="main", choices=("main", "subagent"))
    bl.add_argument("--all", action="store_true", help="one line per project")
    bl.add_argument("--json", action="store_true", help="summaries, outliers and raw values")
    bl.add_argument("--no-save", action="store_true", help="do not store the baseline")
    bl.set_defaults(fn=cmd_baseline)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
