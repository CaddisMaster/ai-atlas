"""One self-contained HTML page, generated locally, with the data baked in.

⚠️ It never leaves the machine, and it makes no requests when opened — no
fonts, no scripts, no images from anywhere. That is not a nicety: the page
carries project paths and command signatures, and `SECURITY.md` cannot follow
it once it is in a browser. The only network-safe version of this page is the
one built from the synthetic demo corpus.

The design rule the mockup got wrong, and this does not: **a refusal is not a
failure.** "Cannot be measured" is the correct answer to most questions this
tool is asked, so it is styled as an ordinary state and never as an error. What
does get an alarming colour is a claim contradicted by the repository.

There is no JavaScript. The rail is anchors, the page is one column, and it
prints.
"""

import html
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from . import PARSER_VERSION, __version__
from .baseline import FLOOR, build
from .config import ABSENT, PRESENT, UNKNOWN, resolve
from .handoff import STALE, find_status_doc
from .handoff import run as handoff_run
from .interventions import MOVED, NOT_TESTED, TOO_FEW, UNDERPOWERED, measure
from .now import look
from .patterns import find
from .report_css import CSS

E = html.escape

STATE_CHIP = {PRESENT: "pine", ABSENT: "mute", UNKNOWN: "brass"}
VERDICT_CHIP = {MOVED: "pine", TOO_FEW: "mute", UNDERPOWERED: "brass", NOT_TESTED: "mute"}


def _num(value: float | int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _stat(label: str, value: str, detail: str = "", tone: str = "") -> str:
    tone = f" {tone}" if tone else ""
    return (f'<div class="stat"><div class="k">{E(label)}</div>'
            f'<div class="v{tone}">{value}</div>'
            f'<div class="d">{E(detail)}</div></div>')


def _sec(title: str, count: str = "") -> str:
    return (f'<div class="sec"><h2>{E(title)}</h2><span class="line"></span>'
            f'<span class="cnt">{E(count)}</span></div>')


def _chip(text: str, tone: str) -> str:
    return f'<span class="chip {tone}">{E(text)}</span>'


def _corpus(conn: sqlite3.Connection, project_root: str) -> dict:
    row = conn.execute("""
        SELECT COUNT(*) sessions,
               (SELECT COUNT(*) FROM messages m JOIN sessions s2 ON s2.id = m.session_id
                 WHERE s2.project_root IS ?) messages,
               (SELECT COUNT(*) FROM tool_calls t JOIN sessions s3 ON s3.id = t.session_id
                 WHERE s3.project_root IS ?) tool_calls,
               MIN(started) first, MAX(ended) last
          FROM sessions WHERE project_root IS ?
    """, (project_root, project_root, project_root)).fetchone()
    return dict(row) if row else {}


def _config_section(resolution) -> str:
    scopes = "".join(
        f"<tr><td class='nm'>{E(scope.name)}</td>"
        f"<td>{_chip(scope.state, STATE_CHIP.get(scope.state, 'mute'))}</td>"
        f"<td class='path'>{E(scope.path or '—')}</td>"
        f"<td>{E(scope.detail)}</td></tr>"
        for scope in resolution.scopes)

    kinds: dict[str, list] = {}
    for item in resolution.items:
        if not item.shadowed:
            kinds.setdefault(item.kind, []).append(item)
    items = "".join(
        f"<tr><td class='nm'>{E(item.name)}</td><td>{E(item.kind)}</td>"
        f"<td>{_chip(item.scope, 'pine')}</td>"
        f"<td class='path'>{E(item.source_path)}</td></tr>"
        for kind in ("agent", "command", "skill", "hook", "mcp", "memory")
        for item in sorted(kinds.get(kind, []), key=lambda i: i.name))

    rules: dict[tuple[str, str], int] = {}
    for rule in resolution.rules:
        rules[(rule.scope, rule.action)] = rules.get((rule.scope, rule.action), 0) + 1
    rule_rows = "".join(
        f"<tr><td class='nm'>{E(action)}</td><td>{_chip(scope, 'pine')}</td>"
        f"<td class='num'>{count}</td></tr>"
        for (scope, action), count in sorted(rules.items()))

    unknown = [s for s in resolution.scopes if s.state == UNKNOWN]
    note = ""
    if unknown:
        listed = ", ".join(f"<b>{E(s.name)}</b>" for s in unknown)
        note = (f'<div class="note"><p>{listed} could not be read, which is not the '
                "same as being empty. A scope we failed to look at is <b>unknown</b>, "
                "and nothing here counts it as absent.</p></div>")

    return f"""
<section id="config">
  <div class="head"><h1>Configuration</h1>
  <p class="sub">Resolved across every scope. Every line carries the file it came from —
  reading one scope and reporting on all of them is how this tool got its first answer
  wrong.</p></div>
  <div class="cluster">
    {_stat("Subagents", str(len(kinds.get("agent", []))))}
    {_stat("Slash commands", str(len(kinds.get("command", []))))}
    {_stat("Skills", str(len(kinds.get("skill", []))))}
    {_stat("Hooks", str(len(kinds.get("hook", []))))}
    {_stat("Permission rules", str(len(resolution.rules)), "across all scopes", "pine")}
  </div>
  {_sec("Every place looked", f"{len(resolution.scopes)} paths")}
  <div class="tbl-wrap"><table>
    <thead><tr><th>Scope</th><th>State</th><th>Path</th><th>Detail</th></tr></thead>
    <tbody>{scopes}</tbody></table></div>
  <div class="legend">
    <span>{_chip("present", "pine")} found and read</span>
    <span>{_chip("absent", "mute")} looked, not there</span>
    <span>{_chip("unknown", "brass")} could not be read</span>
  </div>
  {note}
  {_sec("What is configured", f"{sum(len(v) for v in kinds.values())} items")}
  <div class="tbl-wrap"><table>
    <thead><tr><th>Name</th><th>Kind</th><th>Scope</th><th>Source</th></tr></thead>
    <tbody>{items or "<tr><td colspan='4'>nothing configured in any readable scope</td></tr>"}</tbody>
  </table></div>
  {_sec("Permission rules", f"{len(resolution.rules)} total")}
  <div class="tbl-wrap"><table>
    <thead><tr><th>Action</th><th>Scope</th><th>Rules</th></tr></thead>
    <tbody>{rule_rows or "<tr><td colspan='3'>none</td></tr>"}</tbody></table></div>
</section>"""


def _baseline_section(base) -> str:
    tone = {"established": "pine", "provisional": "brass", "unknown": "mute"}[base.confidence]
    if not base.states_a_norm:
        headline = (f"{base.n} session(s) is not a sample — a norm needs {FLOOR}. "
                    "No normal band is stated, and no session is called unusual.")
    else:
        headline = (f"Based on {base.n} sessions. The band is the Tukey fence; a session "
                    "outside it is unusual on that metric, which is a fact and not a verdict.")

    rows = "".join(
        f"<tr><td class='nm'>{E(s.metric)}</td><td class='num'>{_num(s.median)}</td>"
        f"<td class='num'>{_num(s.p25)} – {_num(s.p75)}</td>"
        f"<td class='num'>{_num(s.low) + ' – ' + _num(s.high) if base.states_a_norm else '—'}</td>"
        f"<td class='num'>{s.n}</td></tr>"
        for s in base.summaries)

    outliers = "".join(
        f"<tr><td class='nm'>{E(o.session_id[:8])}</td><td>{E(o.metric)}</td>"
        f"<td class='num'>{_num(o.value)}</td><td>{E(o.direction)}</td>"
        f"<td class='num'>{_num(o.band[0])} – {_num(o.band[1])}</td></tr>"
        for o in sorted(base.outliers, key=lambda o: o.session_id))

    excluded = "".join(
        f"<tr><td class='nm'>{E(sid[:8])}</td><td>{E(reason)}</td></tr>"
        for sid, reason in base.excluded)

    return f"""
<section id="baseline">
  <div class="head"><h1>What a normal session looks like</h1>
  <p class="sub">{E(headline)}</p></div>
  <div class="cluster">
    {_stat("Sessions counted", str(base.n))}
    {_stat("Excluded", str(len(base.excluded)), "recorded, never dropped")}
    {_stat("Confidence", f'<span class="chip {tone}">{E(base.confidence)}</span>')}
  </div>
  {_sec("Metrics", f"{len(base.summaries)} measured")}
  <div class="tbl-wrap"><table>
    <thead><tr><th>Metric</th><th>Median</th><th>Middle half</th>
    <th>Normal band</th><th>n</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  {_sec("Unusual sessions", f"{len({o.session_id for o in base.outliers})} sessions")
    if base.states_a_norm else ""}
  {"<div class='tbl-wrap'><table><thead><tr><th>Session</th><th>Metric</th><th>Value</th>"
   "<th>Direction</th><th>Band</th></tr></thead><tbody>" + outliers + "</tbody></table></div>"
   if outliers else ""}
  {_sec("Excluded", f"{len(base.excluded)}") if excluded else ""}
  {"<div class='tbl-wrap'><table><thead><tr><th>Session</th><th>Why</th></tr></thead>"
   "<tbody>" + excluded + "</tbody></table></div>" if excluded else ""}
</section>"""


def _patterns_section(report) -> str:
    cards = "".join(f"""
  <div class="card">
    <h3>{_chip(pattern.proposal, "pine")}
      <span style="font-family:var(--mono);font-size:12px;color:var(--ink-3)">
      lift {pattern.lift:.0f}</span></h3>
    <p class="seq">{E(pattern.text)}</p>
    <div class="evidence"><span><b>{pattern.support}</b> sessions</span>
      <span><b>{pattern.count}</b> occurrences</span>
      <span>{E(pattern.why)}</span>
      <span>first at <b>{E(pattern.occurrences[0].session_id[:8])}</b>
        message {E(pattern.occurrences[0].message_uuid[:8])}</span></div>
  </div>""" for pattern in report.patterns[:6])

    permissions = "".join(
        f"<tr><td class='nm'>{E(p.signature)}</td><td class='num'>{p.calls:,}</td>"
        f"<td class='num'>{p.sessions}</td><td class='nm'>{E(p.rule)}</td></tr>"
        for p in report.permissions[:8])

    notes = "".join(f'<div class="note"><p>{E(note)}</p></div>' for note in report.notes)

    return f"""
<section id="patterns">
  <div class="head"><h1>Work that repeats</h1>
  <p class="sub">Ranked by lift — how much more often a sequence happens than its parts'
  own frequencies predict. The most <em>frequent</em> pairs are usually meaningless: two
  common tools land next to each other by arithmetic.</p></div>
  <div class="cluster">
    {_stat("Sessions read", str(report.n_sessions))}
    {_stat("Tool calls", f"{report.n_calls:,}")}
    {_stat("Sequences", str(len(report.patterns)), "above the lift floor")}
    {_stat("Uncovered calls", str(len(report.permissions)), "no allow rule matches", "brass")}
  </div>
  {_sec("Sequences", f"{len(report.patterns)} found") if report.patterns else ""}
  {cards or "<div class='card'><p>No sequence repeats across enough sessions to be a "
             "pattern rather than a coincidence.</p></div>"}
  {_sec("Repeated calls no rule covers", f"{len(report.permissions)}") if permissions else ""}
  {"<div class='tbl-wrap'><table><thead><tr><th>Call</th><th>Times</th><th>Sessions</th>"
   "<th>Rule that would cover it</th></tr></thead><tbody>" + permissions +
   "</tbody></table></div>" if permissions else ""}
  {notes}
</section>"""


def _interventions_section(conn, project_root) -> str:
    rows = conn.execute(
        "SELECT * FROM interventions WHERE project_root IS ? ORDER BY happened DESC",
        (project_root,)).fetchall()
    if not rows:
        return """
<section id="interventions">
  <div class="head"><h1>Did that change help?</h1>
  <p class="sub">Nothing recorded yet. <code>atlas intervention detect</code> proposes
  candidates from config snapshots and file times; <code>atlas apply</code> records one
  automatically when it writes.</p></div>
</section>"""

    cards = []
    for row in rows:
        result = measure(conn, dict(row))
        tested = [r for r in result.results if r.verdict not in (TOO_FEW, NOT_TESTED)]
        if tested:
            body = "".join(
                f"<tr><td class='nm'>{E(r.metric)}</td>"
                f"<td class='num'>{_num(r.median_before)}</td>"
                f"<td class='num'>{_num(r.median_after)}</td>"
                f"<td class='num'>{r.p_value:.3f}</td>"
                f"<td class='num'>{r.n_before}/{r.n_after}</td>"
                f"<td>{_chip(r.verdict, VERDICT_CHIP.get(r.verdict, 'mute'))}</td></tr>"
                for r in sorted(tested, key=lambda r: r.p_value or 1))
            table = ("<div class='tbl-wrap'><table><thead><tr><th>Metric</th><th>Before</th>"
                     "<th>After</th><th>p</th><th>n</th><th>Verdict</th></tr></thead>"
                     f"<tbody>{body}</tbody></table></div>")
        else:
            before = max((r.n_before for r in result.results), default=0)
            after = max((r.n_after for r in result.results), default=0)
            table = (f"<p>{_chip('cannot be measured', 'mute')} "
                     f"{before} session(s) before, {after} after.</p>")

        notes = "".join(f"<span>{E(note)}</span>" for note in result.notes)
        cards.append(f"""
  <div class="card">
    <h3>{E(row["what"])}</h3>
    <p>landed {E(result.happened[:16].replace("T", " "))} UTC
      · recorded via {E(row["source"])}</p>
    {table}
    {f'<p><b>Hoped for:</b> {E(row["expectation"])} — recorded, never scored.</p>'
     if row["expectation"] else ""}
    <div class="evidence">{notes}</div>
  </div>""")

    return f"""
<section id="interventions">
  <div class="head"><h1>Did that change help?</h1>
  <p class="sub">Sessions either side of a change, compared with an exact permutation test
  on three metrics chosen in advance. Six sessions either side are needed before any
  verdict is reachable — a comparison that could not have found anything says so.</p></div>
  {"".join(cards)}
</section>"""


def _now_section(now) -> str:
    if now is None:
        return ""
    placements = "".join(
        f"<tr><td class='nm'>{E(p.metric)}</td><td class='num'>{_num(p.value)}</td>"
        f"<td class='num'>{_num(p.median)}</td>"
        f"<td class='num'>{p.percentile}</td><td class='num'>{p.n}</td>"
        f"<td>{_chip('outside the band', 'brass') if p.outside_band else ''}</td></tr>"
        for p in sorted(now.placements, key=lambda p: p.metric))
    notes = "".join(f'<div class="note"><p>{E(note)}</p></div>' for note in now.notes)

    return f"""
<section id="now">
  <div class="head"><h1>The session being written</h1>
  <p class="sub">A snapshot from when this page was generated. One session is n = 1, so
  everything here is a fact placed among earlier sessions — never a judgement about how
  it is going.</p></div>
  <div class="cluster">
    {_stat("Session", E((now.session_id or "—")[:8]))}
    {_stat("User turns", str(now.user_turns))}
    {_stat("Assistant turns", str(now.assistant_turns))}
    {_stat("Tool calls", str(now.tool_calls))}
  </div>
  {f'<div class="card"><p class="seq">{E(" → ".join(now.recent))}</p>'
   f'<div class="evidence"><span><b>most recent calls</b></span></div></div>'
   if now.recent else ""}
  {"<div class='tbl-wrap'><table><thead><tr><th>Metric</th><th>Now</th><th>Median here</th>"
   "<th>Percentile</th><th>of n</th><th></th></tr></thead><tbody>" + placements +
   "</tbody></table></div>" if placements else ""}
  {notes}
</section>"""


def _handoff_section(report) -> str:
    if report is None:
        return ""
    stale = [f for f in report.findings if f.state == STALE]
    unknown = [f for f in report.findings if f.state == UNKNOWN]
    rows = "".join(
        f"<tr><td class='nm'>{E(f.check)}</td><td>{E(f.subject)}</td>"
        f"<td>{E(f.claim)}</td><td>{E(f.actual)}</td>"
        f"<td class='path'>{E(f.source)}</td></tr>"
        for f in sorted(stale + unknown, key=lambda f: (f.state != STALE, f.check)))

    return f"""
<section id="handoff">
  <div class="head"><h1>What the status document gets wrong</h1>
  <p class="sub">Checked against git, the changelog, the test collector and the
  filesystem. This is the one screen where a colour means something is wrong rather than
  merely unknown.</p></div>
  <div class="cluster">
    {_stat("Checks run", str(len(report.findings)))}
    {_stat("Contradicted", str(len(stale)), "claims the repo disagrees with",
           "clay" if stale else "pine")}
    {_stat("Unknown", str(len(unknown)), "could not be checked", "brass")}
  </div>
  {"<div class='tbl-wrap'><table><thead><tr><th>Check</th><th>Subject</th><th>Claims</th>"
   "<th>Reality</th><th>At</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
   if rows else "<div class='card'><p>Nothing in the status document contradicts the "
                "repository.</p></div>"}
</section>"""


def render(conn, project_root: str, *, root: Path | None = None, synthetic: bool = False,
           include_now: bool = True, title: str = "") -> str:
    """The whole page, as one string."""
    project = Path(project_root)
    resolution = resolve(project, root=root)
    base = build(conn, project_root)
    patterns = find(conn, project_root)
    corpus = _corpus(conn, project_root)
    now = look(conn, root=root) if include_now else None
    if now is not None and now.project_root != project_root:
        now = None
    handoff = handoff_run(project) if find_status_doc(project) else None

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    name = title or f"Atlas — {project.name}"
    banner = ("" if not synthetic else """
  <div class="banner"><b>Synthetic corpus.</b>
  <p>Every number on this page comes from transcripts this program generated. No real
  session, prompt, command or file path appears anywhere in it — which is what makes this
  version safe to publish, and the version built from real transcripts strictly local.</p>
  </div>""")

    nav = "".join(
        f'<a href="#{anchor}"><span>{E(label)}</span><span class="n">{E(count)}</span></a>'
        for anchor, label, count in [
            ("config", "Configuration", str(len(resolution.items))),
            ("handoff", "Handoff", str(len([f for f in handoff.findings if f.state == STALE]))
             if handoff else "—"),
            ("patterns", "Patterns", str(len(patterns.patterns))),
            ("baseline", "Baseline", base.confidence[:4]),
            ("interventions", "Changes", ""),
            ("now", "Now", "live" if now else "—"),
        ] if anchor != "now" or now)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(name)}</title>
<style>{CSS}</style>
</head><body>
<div class="app">
  <aside class="rail">
    <div class="brand"><b>Atlas</b><span>{E(generated)}</span></div>
    <nav class="nav">{nav}</nav>
    <div class="rail-foot"><p>Read from <code>~/.claude</code> on this machine.
    This page makes no network requests — not even for fonts.</p></div>
  </aside>
  <main class="main">
    {banner}
    <div class="head"><h1>{E(project.name)}</h1>
      <p class="sub">{E(str(project))}</p></div>
    <div class="cluster">
      {_stat("Sessions", str(corpus.get("sessions") or 0))}
      {_stat("Messages", f"{corpus.get('messages') or 0:,}")}
      {_stat("Tool calls", f"{corpus.get('tool_calls') or 0:,}")}
      {_stat("First seen", (corpus.get("first") or "—")[:10])}
      {_stat("Last seen", (corpus.get("last") or "—")[:10])}
    </div>
    {_handoff_section(handoff)}
    {_config_section(resolution)}
    {_patterns_section(patterns)}
    {_baseline_section(base)}
    {_interventions_section(conn, project_root)}
    {_now_section(now)}
    <div class="foot">
      <p>Generated by <code>atlas report</code> — ai-atlas {E(__version__)},
      parser v{PARSER_VERSION}. Every figure is computed by the application; nothing on
      this page was written by a model. Where a number is missing, the tool decided it
      could not be supported rather than estimating it.</p>
    </div>
  </main>
</div>
</body></html>
"""
