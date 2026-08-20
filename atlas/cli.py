"""Command line entry point: ``python -m atlas <command>``."""

import argparse
import sys

from . import PARSER_VERSION, __version__
from .db import connect
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atlas", description="Measure how you work with Claude Code.")
    p.add_argument("--version", action="version", version=f"ai-atlas {__version__} (parser v{PARSER_VERSION})")
    p.add_argument("--db", default=None, help="database path (default: ~/.local/share/ai-atlas/atlas.db)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="read new transcript content into the database").set_defaults(fn=cmd_ingest)
    sub.add_parser("stats", help="summarise what has been ingested").set_defaults(fn=cmd_stats)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
