"""A change to how you work, and whether the numbers moved.

This is what the project is for. Everything before it — ingest, config,
baselines, patterns — exists so that this sentence can be true or false rather
than a feeling: *"adding that rule made sessions shorter."*

⚠️ The honest answer is usually "cannot tell yet", and it has to be as easy to
reach as a verdict. The best-covered project in the corpus has ten usable
sessions. Split around a change made halfway through, that is four sessions
against six, and four against six will only separate if the effect is enormous.
A tool that returns a verdict anyway is worse than no tool: it launders noise
into evidence, and the evidence is about the user's own working habits, which
they will act on.

So:

1. **A metric with fewer than ``MIN_SIDE`` sessions on either side gets no
   verdict at all.** Not a weak verdict. None.
1b. **And a split that could not reach the threshold however the data fell is
   said to be exactly that.** Three sessions against three cannot produce a
   p-value below 0.2 — four relabellings always tie with the real one — so a
   test on those numbers is theatre. The tool computes the smallest p the split
   sizes *admit* and, when that is above the threshold, reports "cannot
   separate at this sample size" rather than "no verdict". The difference
   matters: one means the change did not show up, the other means the
   experiment could not have shown it.
2. **Significance is an exact permutation test**, not a t-test: n is tiny, the
   distributions are not normal, and with these numbers every split can be
   enumerated. No sampling, no seed, no distributional assumption — the p-value
   is the exact fraction of relabellings that separate at least as well.
3. **Three metrics are tested, chosen in advance.** Testing everything measured
   and correcting for all of it was self-defeating: at thirteen metrics the
   threshold is 0.0038, which needs eight sessions either side before any
   verdict is reachable. At three it is 0.0167, reachable at six.

   Choosing metrics *before* looking is not the same as choosing them after —
   the second is how a result gets manufactured. So the three are fixed here,
   frozen under ``INTERVENTION_VERSION``, and every other metric is still shown
   with its before and after and explicitly **not tested**.

Definitions frozen under ``INTERVENTION_VERSION``.
"""

import itertools
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from math import comb
from pathlib import Path

from .baseline import BASELINE_VERSION, build

# v2 — three pre-registered metrics instead of every metric measured. Results
# computed under v1 corrected for thirteen and are not comparable with these.
INTERVENTION_VERSION = 2

# Pre-registered, in advance and on purpose. One measure of each thing an
# intervention plausibly changes:
#
#   duration_min     how long a session takes
#   user_turns       how much steering the human had to do
#   tools_per_turn   how much the assistant got done per turn
#
# `tool_calls` and `assistant_turns` are deliberately absent: they are close to
# linear in duration, so testing them adds correction without adding evidence.
# Token counts move with model and context behaviour more than with anything a
# person changes. Everything not listed is still measured, still shown, and
# never tested — see decisions/0012.
PREREGISTERED = ("duration_min", "user_turns", "tools_per_turn")

MIN_SIDE = 3          # sessions either side, below which no verdict is offered
ALPHA = 0.05
MAX_EXACT = 200_000   # splits to enumerate before falling back to sampling
SAMPLES = 20_000
SEED = 20260821       # only used above MAX_EXACT; recorded so a run is repeatable

KINDS = ("rule", "hook", "command", "skill", "agent", "setting", "memory", "mcp", "other")

MOVED, NO_VERDICT, TOO_FEW = "moved", "no verdict", "not enough sessions"
NOT_TESTED = "not pre-registered"
UNDERPOWERED = "cannot separate at this sample size"

# Sessions needed either side before any verdict is reachable at all, at the
# corrected threshold. Measured, not assumed — see smallest_p. Three metrics
# rather than thirteen moved this from eight to six.
REACHABLE_AT = 6


@dataclass(frozen=True)
class Result:
    metric: str
    n_before: int
    n_after: int
    median_before: float | None
    median_after: float | None
    delta: float | None
    p_value: float | None
    verdict: str

    @property
    def direction(self) -> str:
        if self.delta is None or self.delta == 0:
            return "—"
        return "up" if self.delta > 0 else "down"


@dataclass
class Measurement:
    intervention_id: int
    happened: str
    results: list[Result] = field(default_factory=list)
    spanning: list[str] = field(default_factory=list)   # sessions in flight at the time
    threshold: float = ALPHA
    notes: list[str] = field(default_factory=list)

    @property
    def moved(self) -> list[Result]:
        return [r for r in self.results if r.verdict == MOVED]


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def record(conn, project_root: str | None, what: str, happened: str, *,
           kind: str = "other", expectation: str = "", source: str = "manual",
           evidence: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO interventions (project_root, happened, kind, what, expectation,"
        " source, evidence, recorded) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (project_root, happened, kind, what, expectation, source, evidence,
         datetime.now(UTC).isoformat()))
    conn.commit()
    return cur.lastrowid


def _session_window(conn, project_root: str | None) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT MIN(started) a, MAX(ended) b FROM sessions WHERE project_root IS ?"
        " AND kind = 'main'", (project_root,)).fetchone()
    return (row["a"], row["b"]) if row else (None, None)


@dataclass(frozen=True)
class Candidate:
    kind: str
    what: str
    happened: str
    source: str
    evidence: str


def from_snapshots(conn, project_root: str | None) -> list[Candidate]:
    """Config changes visible between two stored snapshots.

    Exact about *what* changed and vague about *when*: all we know is that it
    happened between one `atlas config` run and the next.
    """
    snaps = conn.execute(
        "SELECT id, taken FROM config_snap WHERE project_root IS ? ORDER BY id",
        (project_root,)).fetchall()
    out: list[Candidate] = []
    for older, newer in itertools.pairwise(snaps):
        def names(snap_id):
            items = {(r["kind"], r["name"]) for r in conn.execute(
                "SELECT kind, name FROM config_items WHERE snap_id = ? AND shadowed = 0",
                (snap_id,))}
            rules = {("rule", r["pattern"]) for r in conn.execute(
                "SELECT pattern FROM rules WHERE snap_id = ?", (snap_id,))}
            return items | rules

        for kind, name in sorted(names(newer["id"]) - names(older["id"])):
            out.append(Candidate(
                kind if kind in KINDS else "other", f"added {kind} {name}",
                newer["taken"], "config-diff",
                f"absent in snapshot {older['id']} ({older['taken'][:10]}), "
                f"present in {newer['id']} ({newer['taken'][:10]})"))
    return out


def from_mtimes(conn, project_root: str | None) -> list[Candidate]:
    """Config files last written *during* the period the sessions cover.

    ⚠️ An mtime says when a file was last written, not what changed or how many
    times it was edited before that. It is a weaker claim than a snapshot diff
    and a much sharper date — which is the only date available at all for any
    change made before this tool existed.
    """
    first, last = _session_window(conn, project_root)
    start, end = _when(first), _when(last)
    if not start or not end:
        return []

    snap = conn.execute(
        "SELECT id FROM config_snap WHERE project_root IS ? ORDER BY id DESC LIMIT 1",
        (project_root,)).fetchone()
    if snap is None:
        return []

    out = []
    seen: set[str] = set()
    for row in conn.execute(
            "SELECT kind, name, source_path FROM config_items WHERE snap_id = ?",
            (snap["id"],)):
        path = Path(row["source_path"])
        if row["source_path"] in seen or not path.exists():
            continue
        seen.add(row["source_path"])
        written = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if not (start < written < end):
            continue
        out.append(Candidate(
            row["kind"] if row["kind"] in KINDS else "other",
            f"{path.name} was last written",
            written.isoformat(), "mtime",
            f"{row['source_path']} — mtime only: what changed is not recorded"))
    return out


def detect(conn, project_root: str | None) -> list[Candidate]:
    candidates = from_snapshots(conn, project_root) + from_mtimes(conn, project_root)
    return sorted(candidates, key=lambda c: c.happened)


def permutation_p(before: list[float], after: list[float]) -> float | None:
    """Exact two-sided p for a difference in medians, by relabelling.

    Of all the ways these sessions could have been split into a group of
    ``len(before)`` and a group of ``len(after)``, what fraction separate the
    medians at least as far as the real split did? No distributional assumption,
    which matters: session metrics are skewed and n is single digits.
    """
    pooled = [*before, *after]
    k = len(before)
    if k == 0 or len(after) == 0:
        return None
    observed = abs(statistics.median(after) - statistics.median(before))
    total = comb(len(pooled), k)

    if total <= MAX_EXACT:
        splits = itertools.combinations(range(len(pooled)), k)
        tried = total
    else:
        import random
        rng = random.Random(SEED)
        splits = (tuple(rng.sample(range(len(pooled)), k)) for _ in range(SAMPLES))
        tried = SAMPLES

    extreme = 0
    for index in splits:
        chosen = set(index)
        left = [pooled[i] for i in chosen]
        right = [pooled[i] for i in range(len(pooled)) if i not in chosen]
        if abs(statistics.median(right) - statistics.median(left)) >= observed - 1e-12:
            extreme += 1
    return extreme / tried


@cache
def smallest_p(n_before: int, n_after: int) -> float | None:
    """The lowest p-value these split sizes can produce, however clean the data.

    Computed rather than derived: run the same permutation test on a perfectly
    separated sample of the same shape.

    ```
    3 vs 3   floor 0.200      6 vs 6   floor 0.013
    4 vs 4   floor 0.057      8 vs 8   floor 0.0031   ← first that clears 0.05÷13
    ```

    So **eight sessions either side** — sixteen around the change — before any
    verdict is reachable at all. The best-covered project in the corpus this was
    written against has ten sessions in total. That is the real scale of this
    measurement, and it is better known before an experiment than after one.
    """
    if n_before < 1 or n_after < 1:
        return None
    return permutation_p([float(i) for i in range(n_before)],
                         [1000.0 + i for i in range(n_after)])


def measure(conn, intervention: dict | None = None, *, intervention_id: int | None = None
            ) -> Measurement:
    if intervention is None:
        intervention = dict(conn.execute(
            "SELECT * FROM interventions WHERE id = ?", (intervention_id,)).fetchone())

    project_root = intervention["project_root"]
    happened = _when(intervention["happened"])
    result = Measurement(intervention_id=intervention["id"],
                         happened=intervention["happened"])

    # Eligibility, exclusions and the metrics themselves are milestone 4's
    # definitions, reused rather than restated — a before/after computed a
    # different way from the baseline it is compared against is not a comparison.
    base = build(conn, project_root)
    starts = {r["id"]: (r["started"], r["ended"]) for r in conn.execute(
        "SELECT id, started, ended FROM sessions WHERE project_root IS ?", (project_root,))}

    before: dict[str, list[float]] = {}
    after: dict[str, list[float]] = {}
    for session_id, values in base.values.items():
        started, ended = starts.get(session_id, (None, None))
        began, finished = _when(started), _when(ended)
        if began is None or happened is None:
            continue
        if began < happened and finished and finished > happened:
            # In flight when the change landed: it saw both worlds, so it
            # belongs to neither side.
            result.spanning.append(session_id)
            continue
        side = before if began < happened else after
        for metric, value in values.items():
            side.setdefault(metric, []).append(value)

    metrics = sorted(set(before) | set(after))
    tested = [m for m in metrics if m in PREREGISTERED]
    result.threshold = ALPHA / len(tested) if tested else ALPHA
    for metric in metrics:
        left, right = before.get(metric, []), after.get(metric, [])
        if metric not in PREREGISTERED:
            # Shown, never tested. Withholding it would hide context; giving it
            # a p-value would invite picking the one that moved.
            result.results.append(Result(metric, len(left), len(right),
                                         _median(left), _median(right),
                                         _delta(left, right), None, NOT_TESTED))
            continue
        if len(left) < MIN_SIDE or len(right) < MIN_SIDE:
            result.results.append(Result(metric, len(left), len(right),
                                         _median(left), _median(right), None, None, TOO_FEW))
            continue
        p = permutation_p(left, right)
        delta = statistics.median(right) - statistics.median(left)
        floor = smallest_p(len(left), len(right))
        if floor is not None and floor > result.threshold:
            verdict = UNDERPOWERED
        elif p is not None and p < result.threshold:
            verdict = MOVED
        else:
            verdict = NO_VERDICT
        result.results.append(Result(metric, len(left), len(right),
                                     statistics.median(left), statistics.median(right),
                                     delta, p, verdict))

    # Only worth saying when something was actually tested: a correction for
    # multiple comparisons is noise on a comparison that never happened.
    context = [r for r in result.results if r.verdict == NOT_TESTED]
    # Only worth explaining when something *was* tested; on a comparison that
    # could not run at all it is one more line of noise.
    if context and any(r.verdict in (MOVED, NO_VERDICT) for r in result.results):
        result.notes.append(
            f"{len(context)} further metric(s) shown for context and not tested — "
            "three are pre-registered, and picking a fourth after seeing it move "
            "is how a result gets manufactured")

    underpowered = [r for r in result.results if r.verdict == UNDERPOWERED]
    if underpowered:
        example = underpowered[0]
        floor = smallest_p(example.n_before, example.n_after)
        result.notes.append(
            f"{example.n_before} against {example.n_after} cannot produce a p below "
            f"{floor:.3f} however the sessions fell, and the threshold is "
            f"{result.threshold:.4f} — this comparison could not have found anything")

    if any(r.verdict in (MOVED, NO_VERDICT) for r in result.results):
        result.notes.append(
            f"{len(tested)} pre-registered metrics, so the threshold is {ALPHA} ÷ "
            f"{len(tested)} = {result.threshold:.4f} — at plain 0.05, one metric in "
            "twenty moves by chance")
    if result.spanning:
        result.notes.append(
            f"{len(result.spanning)} session(s) were in flight when this landed and "
            "belong to neither side")
    return result


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _delta(before: list[float], after: list[float]) -> float | None:
    if not before or not after:
        return None
    return statistics.median(after) - statistics.median(before)


def save(conn, measurement: Measurement) -> None:
    conn.execute("DELETE FROM intervention_results WHERE intervention_id = ?"
                 " AND intervention_version = ?",
                 (measurement.intervention_id, INTERVENTION_VERSION))
    conn.executemany(
        "INSERT INTO intervention_results (intervention_id, metric, n_before, n_after,"
        " median_before, median_after, delta, p_value, verdict, threshold,"
        " intervention_version, baseline_version, computed)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(measurement.intervention_id, r.metric, r.n_before, r.n_after, r.median_before,
          r.median_after, r.delta, r.p_value, r.verdict, measurement.threshold,
          INTERVENTION_VERSION, BASELINE_VERSION, datetime.now(UTC).isoformat())
         for r in measurement.results])
    conn.commit()
