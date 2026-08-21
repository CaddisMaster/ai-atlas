"""Intervention acceptance tests.

This is the sentence the whole project exists to make checkable: *"that change
made things better."* Most of these tests are about the times it cannot be
said — because with ten sessions in the best-covered real project, that is most
of the time, and a tool that returns a verdict anyway launders noise into
evidence about somebody's own working habits.
"""

import pytest

from atlas.interventions import (
    ALPHA,
    MIN_SIDE,
    MOVED,
    NO_VERDICT,
    TOO_FEW,
    UNDERPOWERED,
    measure,
    permutation_p,
    record,
    save,
    smallest_p,
)
from tests.conftest import add_session

WHEN = "2026-08-18T12:00:00+00:00"
QUIET = {"tools": ["Bash:grep"] * 10, "usage": {"input": 100, "output": 1000,
                                               "cache_read": 9000}}


def _session(conn, name, day, *, minutes, **kw):
    add_session(conn, name, started=f"2026-08-{day:02d}T09:00:00+00:00",
                minutes=minutes, user=10, assistant=20, **{**QUIET, **kw})


def _record(conn, **kw):
    return record(conn, "/work/demo-app", kw.pop("what", "added a rule"),
                  kw.pop("happened", WHEN), **kw)


def test_a_thin_side_gets_no_verdict_at_all(conn):
    """Two sessions before and seven after is the real corpus, and the answer
    is "cannot be measured" — not a weak verdict, none."""
    for i, day in enumerate((14, 15)):
        _session(conn, f"before{i}", day, minutes=100.0)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25)):
        _session(conn, f"after{i}", day, minutes=20.0)

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    assert {r.verdict for r in result.results} == {TOO_FEW}
    assert all(r.p_value is None for r in result.results), "no p-value without a test"


def test_a_real_change_is_reported_when_the_sessions_can_carry_it(conn):
    """Eight against eight, separated with no overlap at all.

    Eight, not six: six against six cannot produce a p below 0.0043, and the
    threshold after correcting for thirteen metrics is 0.0038.
    """
    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=100.0 + i)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=10.0 + i)

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    duration = next(r for r in result.results if r.metric == "duration_min")
    assert duration.verdict == MOVED
    assert duration.direction == "down"
    assert duration.p_value < result.threshold


def test_a_difference_inside_the_noise_gets_no_verdict(conn):
    """The outcome that has to be as easy to reach as a verdict."""
    minutes_before = (100.0, 20.0, 60.0, 90.0, 30.0, 70.0, 45.0, 80.0)
    minutes_after = (95.0, 25.0, 55.0, 85.0, 35.0, 65.0, 50.0, 75.0)
    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=minutes_before[i])
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=minutes_after[i])

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    duration = next(r for r in result.results if r.metric == "duration_min")
    assert duration.verdict == NO_VERDICT
    assert duration.p_value > result.threshold
    assert result.moved == []


def test_the_threshold_is_corrected_for_the_metrics_tested(conn):
    """Thirteen metrics at p < 0.05 turns up one by chance. The reader is told
    the corrected threshold and shown the uncorrected p."""
    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=100.0 + i)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=10.0 + i)

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    tested = [r for r in result.results if r.verdict != TOO_FEW]
    assert result.threshold == pytest.approx(ALPHA / len({r.metric for r in result.results}))
    assert result.threshold < ALPHA
    assert any("threshold" in note for note in result.notes)
    assert tested, "something has to have been tested for the correction to matter"


def test_a_session_in_flight_belongs_to_neither_side(conn):
    """A session that started before the change and ended after it saw both
    worlds. Counting it either way is a lie about which world it was in."""
    for i, day in enumerate((10, 11, 12)):
        _session(conn, f"before{i}", day, minutes=100.0)
    add_session(conn, "spanning", started="2026-08-18T09:00:00+00:00",
                minutes=24 * 60, user=10, assistant=20, **QUIET)
    for i, day in enumerate((20, 21, 22)):
        _session(conn, f"after{i}", day, minutes=20.0)

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    assert result.spanning == ["spanning"]
    duration = next(r for r in result.results if r.metric == "duration_min")
    assert duration.n_before == 3 and duration.n_after == 3


def test_the_permutation_test_is_exact_and_two_sided():
    """No sampling and no seed at these sizes: every relabelling is enumerated.

    Three against three, perfectly separated, gives 4/20 = 0.2 — the original
    grouping, its mirror, and two relabellings whose medians tie with it. No
    arrangement of three against three does better, which is the finding that
    produced the "cannot separate at this sample size" verdict.
    """
    assert permutation_p([1.0, 2.0, 3.0], [10.0, 11.0, 12.0]) == pytest.approx(4 / 20)
    assert permutation_p([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_a_split_that_could_never_separate_says_so(conn):
    """Three against three cannot produce a p below 0.2 whatever the data does.

    Reporting "no verdict" there says the change did nothing. The truth is that
    the experiment could not have found anything, and those are different
    sentences.
    """
    for i, day in enumerate((10, 11, 12)):
        _session(conn, f"before{i}", day, minutes=500.0 + i)
    for i, day in enumerate((20, 21, 22)):
        _session(conn, f"after{i}", day, minutes=1.0 + i)

    result = measure(conn, {"id": 1, "project_root": "/work/demo-app", "happened": WHEN})
    duration = next(r for r in result.results if r.metric == "duration_min")
    assert duration.verdict == UNDERPOWERED
    assert duration.p_value == pytest.approx(0.2), "perfectly separated, and still 0.2"
    assert any("could not have found anything" in note for note in result.notes)


@pytest.mark.parametrize("n,expected_floor", [
    (3, 0.20000),
    (5, 0.04762),   # still above a plain 0.05 only just — and far above corrected
    (8, 0.00311),   # the first symmetric split that can clear 0.05 ÷ 13
])
def test_the_reachable_floor_comes_out_of_the_sample_size(n, expected_floor):
    """**Eight sessions each side** — sixteen around the change — before any
    verdict is reachable at all, once the threshold is corrected for thirteen
    metrics. The best-covered project in the real corpus has ten sessions in
    total. That is the honest scale of this measurement, and it is better known
    before an experiment than after one.
    """
    assert smallest_p(n, n) == pytest.approx(expected_floor, rel=0.01)


def test_the_smallest_measurable_sample_is_stated_not_assumed():
    """MIN_SIDE is a definition, and it is the one that decides how often this
    tool can say anything at all."""
    assert MIN_SIDE == 3


def test_results_carry_both_versions_they_depend_on(conn):
    """A comparison depends on how the metrics were computed *and* on how the
    comparison was made. Rows either side of a change to either are not
    comparable."""
    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=100.0 + i)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=10.0 + i)
    intervention_id = _record(conn)

    save(conn, measure(conn, intervention_id=intervention_id))
    row = conn.execute(
        "SELECT intervention_version, baseline_version, threshold FROM intervention_results"
        " WHERE intervention_id = ? LIMIT 1", (intervention_id,)).fetchone()
    assert row["intervention_version"] == 1 and row["baseline_version"] == 1
    assert row["threshold"] < ALPHA


def test_what_the_human_hoped_for_is_recorded_and_never_scored(conn):
    """An expectation is context for the reader, not an input to the maths.

    Scoring against it would be exactly the trap: deciding whether the numbers
    agree with what somebody already believed.
    """
    intervention_id = _record(conn, expectation="fewer permission prompts")
    row = conn.execute("SELECT expectation FROM interventions WHERE id = ?",
                       (intervention_id,)).fetchone()
    assert row["expectation"] == "fewer permission prompts"

    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=100.0 + i)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=10.0 + i)
    result = measure(conn, intervention_id=intervention_id)
    assert all("prompt" not in (r.metric or "") for r in result.results)


def test_measuring_twice_replaces_rather_than_accumulates(conn):
    for i, day in enumerate((1, 2, 3, 4, 5, 6, 7, 8)):
        _session(conn, f"before{i}", day, minutes=100.0 + i)
    for i, day in enumerate((19, 20, 21, 22, 23, 24, 25, 26)):
        _session(conn, f"after{i}", day, minutes=10.0 + i)
    intervention_id = _record(conn)

    save(conn, measure(conn, intervention_id=intervention_id))
    first = conn.execute("SELECT COUNT(*) n FROM intervention_results").fetchone()["n"]
    save(conn, measure(conn, intervention_id=intervention_id))
    assert conn.execute("SELECT COUNT(*) n FROM intervention_results").fetchone()["n"] == first
