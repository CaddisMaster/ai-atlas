"""Baseline acceptance tests.

The acceptance criterion has two halves and the second is the hard one: state
what a normal session looks like, **and** say how confident that is. Ten
sessions over a week is not a sample, and a tool that reports a median without
saying so is inviting somebody to act on noise.

So most of these tests are about the refusals.
"""

import pytest

from atlas.baseline import BASELINE_VERSION, ESTABLISHED, FLOOR, build, save, summarise
from tests.conftest import add_session

NORMAL = {"user": 100, "assistant": 200, "minutes": 120.0,
          "tools": ["Bash"] * 90 + ["Edit"] * 6 + ["Read"] * 4,
          "usage": {"input": 1000, "output": 500_000, "cache_read": 99_000}}


def _corpus(conn, n=6, **overrides):
    for i in range(n):
        add_session(conn, f"s{i}", **{**NORMAL, **overrides})


def test_a_sample_below_the_floor_states_no_norm(conn):
    """Four sessions is not a normal. Saying so is the feature."""
    _corpus(conn, n=FLOOR - 1)
    base = build(conn, "/work/demo-app")

    assert base.confidence == "unknown"
    assert not base.states_a_norm
    assert base.outliers == [], "no band means no outlier claims"
    assert base.summaries, "the numbers are still shown; only the norm is withheld"


@pytest.mark.parametrize("n,expected", [
    (FLOOR - 1, "unknown"),
    (FLOOR, "provisional"),
    (ESTABLISHED - 1, "provisional"),
    (ESTABLISHED, "established"),
])
def test_confidence_comes_from_n_alone(conn, n, expected):
    _corpus(conn, n=n)
    assert build(conn, "/work/demo-app").confidence == expected


def test_a_session_with_no_assistant_turns_is_excluded_and_recorded(conn):
    """Three of thirteen real sessions are a prompt typed and abandoned.

    Counting them drags every median toward zero; dropping them quietly is the
    thing this project exists not to do.
    """
    _corpus(conn, n=5)
    add_session(conn, "abandoned", user=2, assistant=0, minutes=0.0)

    base = build(conn, "/work/demo-app")
    assert base.excluded == [("abandoned", "no assistant turns")]
    assert "abandoned" not in base.counted
    assert base.n == 5


def test_subagents_are_not_mixed_into_the_main_baseline(conn):
    """A subagent session is a different animal — short, tool-dense, unattended."""
    _corpus(conn, n=6)
    for i in range(4):
        add_session(conn, f"agent-{i}", kind="subagent", user=8, assistant=15,
                    minutes=2.0, tools=["Grep"] * 7)

    main = build(conn, "/work/demo-app", kind="main")
    sub = build(conn, "/work/demo-app", kind="subagent")
    assert main.n == 6 and sub.n == 4
    assert main.summary("assistant_turns").median == 200
    assert sub.confidence == "unknown", "four subagents is still not a sample"


def test_a_session_outside_the_band_is_named(conn):
    _corpus(conn, n=7)
    add_session(conn, "marathon", user=100, assistant=200, minutes=1200.0,
                tools=NORMAL["tools"], usage=NORMAL["usage"])

    base = build(conn, "/work/demo-app")
    outlier = next(o for o in base.outliers if o.metric == "duration_min")
    assert outlier.session_id == "marathon"
    assert outlier.direction == "high"
    assert outlier.value == pytest.approx(1200.0)


def test_tool_mix_is_measured_per_session_not_pooled(conn):
    """Pooling counts across a project lets the longest session define "normal".

    Five short editing sessions and one enormous Bash session: pooled, the
    project looks like Bash. Per session, the normal session is an editing one.
    """
    for i in range(5):
        add_session(conn, f"edit{i}", tools=["Edit"] * 8 + ["Bash"] * 2,
                    user=10, assistant=20, minutes=15.0)
    add_session(conn, "giant", tools=["Bash"] * 2000, user=200, assistant=400, minutes=300.0)

    base = build(conn, "/work/demo-app")
    assert base.summary("share_Edit").median == pytest.approx(0.8)
    assert base.summary("share_Bash").median == pytest.approx(0.2)


def test_each_metric_carries_its_own_n(conn):
    """A session missing one value is absent from that metric, not from the rest."""
    _corpus(conn, n=6)
    conn.execute("UPDATE messages SET ts = NULL WHERE session_id = 's0'")
    conn.execute("UPDATE sessions SET started = NULL, ended = NULL WHERE id = 's0'")
    conn.commit()

    base = build(conn, "/work/demo-app")
    assert base.summary("duration_min").n == 5
    assert base.summary("tool_calls").n == 6


def test_quartiles_use_the_documented_convention(conn):
    """The quantile convention is part of the measurement, so it is pinned.

    `statistics.quantiles(method="inclusive")` on 1..9 gives 3, 5, 7. The
    exclusive method gives 2.5, 5, 7.5 — different bands, different outliers,
    from the same sessions.
    """
    summary = summarise("x", [float(v) for v in range(1, 10)])
    assert (summary.p25, summary.median, summary.p75) == (3, 5, 7)
    assert (summary.low, summary.high) == (0, 13)


def test_a_rate_band_never_exceeds_one(conn):
    """A cache hit rate of 101% is not a thing a reader should have to interpret."""
    _corpus(conn, n=6)
    base = build(conn, "/work/demo-app")
    assert base.summary("cache_hit_rate").high <= 1.0
    assert base.summary("share_Bash").high <= 1.0


def test_the_low_fence_is_clamped_at_zero(conn):
    _corpus(conn, n=6)
    base = build(conn, "/work/demo-app")
    assert all(s.low >= 0 for s in base.summaries)


def test_stored_rows_carry_the_baseline_version(conn):
    """Rows either side of a definition change are not comparable, and the
    database has to be able to say which definition produced a number."""
    _corpus(conn, n=6)
    baseline_id, is_new = save(conn, build(conn, "/work/demo-app"))
    assert is_new

    row = conn.execute("SELECT baseline_version FROM baselines WHERE id = ?",
                       (baseline_id,)).fetchone()
    assert row["baseline_version"] == BASELINE_VERSION
    versions = {r["baseline_version"] for r in
                conn.execute("SELECT DISTINCT baseline_version FROM session_metrics")}
    assert versions == {BASELINE_VERSION}


def test_exclusions_survive_into_the_database(conn):
    _corpus(conn, n=5)
    add_session(conn, "abandoned", user=2, assistant=0, minutes=0.0)
    baseline_id, _ = save(conn, build(conn, "/work/demo-app"))

    rows = conn.execute("SELECT session_id, reason FROM baseline_exclusions WHERE baseline_id = ?",
                        (baseline_id,)).fetchall()
    assert [(r["session_id"], r["reason"]) for r in rows] == [("abandoned", "no assistant turns")]


def test_an_unchanged_rerun_is_not_a_new_baseline(conn):
    _corpus(conn, n=6)
    first, is_new = save(conn, build(conn, "/work/demo-app"))
    assert is_new
    again, is_new = save(conn, build(conn, "/work/demo-app"))
    assert (again, is_new) == (first, False)

    add_session(conn, "extra", **NORMAL)
    third, is_new = save(conn, build(conn, "/work/demo-app"))
    assert is_new and third != first
