"""Pattern detection acceptance tests.

Detection is deterministic: it counts. The tests that matter are the ones that
stop it counting the wrong thing — a coincidence, a repetition, or a habit that
happened once in one session and never again.
"""

from atlas.config import resolve
from atlas.config import save as config_save
from atlas.patterns import MIN_LIFT, MIN_SUPPORT, PATTERN_VERSION, find, save
from tests.conftest import add_session

RITUAL = ["Bash:git add", "Bash:git push", "Bash:gh pr"]
# Two common tools, interleaved without a fixed rhythm — the shape of `grep`
# and `sed` in the corpus, where every pairing of them is arithmetic.
NOISE = ["Bash:grep", "Bash:sed", "Bash:grep", "Bash:grep", "Bash:sed", "Bash:sed",
         "Bash:grep", "Bash:sed", "Bash:sed", "Bash:grep", "Bash:grep", "Bash:sed"]


def noise(i):
    """Different surroundings per session, as real sessions have.

    Identical context either side of a ritual makes the longer window just as
    frequent as the ritual, and the longest-wins rule then reports
    `sed → git add → git push → gh pr` — the ritual plus whatever happened to
    precede it. Real sessions vary; the fixture has to as well.
    """
    return NOISE[i % len(NOISE):] + NOISE[:i % len(NOISE)]


def _texts(report):
    return [p.text for p in report.patterns]


def test_a_sequence_in_three_sessions_is_found(conn):
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])

    report = find(conn, "/work/demo-app")
    assert "Bash:git add → Bash:git push → Bash:gh pr" in _texts(report)


def test_a_sequence_in_too_few_sessions_is_not_a_pattern(conn):
    """One session doing something twice is a day, not a habit."""
    add_session(conn, "s0", tools=[*RITUAL, *noise(0), *RITUAL])
    add_session(conn, "s1", tools=noise(3))

    report = find(conn, "/work/demo-app")
    assert _texts(report) == []
    assert any("2 session" in note for note in report.notes)


def test_calls_that_merely_co_occur_are_not_a_pattern(conn):
    """The frequency trap, as a test.

    `grep → sed` is the most common pair in the corpus — eight sessions, fifty
    occurrences — and it means nothing: both tools are everywhere, so they land
    next to each other by arithmetic. Ranking by frequency buries the rituals
    under pairs like this one.
    """
    for i in range(4):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])

    report = find(conn, "/work/demo-app")
    assert "Bash:grep → Bash:sed" not in _texts(report)
    assert all(p.lift >= MIN_LIFT for p in report.patterns)
    assert report.patterns[0].text.startswith("Bash:git add")


def test_consecutive_repeats_are_collapsed(conn):
    """How many times in a row you grepped varies. The shape is what repeats."""
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), "Bash:grep", "Bash:grep", "Bash:grep",
                                          "Write:.py", "Bash:test.sh", *noise(i + 5)])

    report = find(conn, "/work/demo-app")
    # The three greps arrive as one, wherever the reported window happens to
    # start — the surrounding context can extend it, the run itself cannot.
    assert any("Bash:grep → Write:.py → Bash:test.sh" in text for text in _texts(report))
    assert not any("Bash:grep → Bash:grep" in text for text in _texts(report))


def test_the_longest_sequence_wins(conn):
    """A three-step habit reported as three overlapping pairs is one habit
    reported four times."""
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])

    report = find(conn, "/work/demo-app")
    assert "Bash:git add → Bash:git push" not in _texts(report)


def test_a_wrap_up_sequence_proposes_a_hook(conn):
    """A ritual that always lands at the end of a session is a hook.

    Nobody should have to remember to type it.
    """
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}",
                    tools=[*noise(i), "Bash:test.sh", "Edit:.md", "Bash:git commit"])

    report = find(conn, "/work/demo-app")
    wrap_up = next(p for p in report.patterns if p.text.startswith("Bash:test.sh"))
    assert wrap_up.proposal == "hook"
    assert "last" in wrap_up.why


def test_occurrences_name_the_message_they_started_at(conn):
    """The claim has to be checkable by hand, against the transcript."""
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])

    pattern = next(p for p in find(conn, "/work/demo-app").patterns
                   if p.text.startswith("Bash:git add"))
    occurrence = pattern.occurrences[0]
    assert occurrence.session_id in {"s0", "s1", "s2"}
    row = conn.execute("SELECT uuid FROM messages WHERE uuid = ?",
                       (occurrence.message_uuid,)).fetchone()
    assert row is not None, "the evidence must point at a message that exists"


def test_a_repeated_uncovered_call_proposes_a_permission(conn, fake_project, fake_home):
    for i in range(3):
        add_session(conn, f"s{i}", project_root=str(fake_project),
                    tools=["Bash:npm run"] * 6)
    config_save(conn, resolve(fake_project, root=fake_home,
                              enterprise=fake_home / "nope.json"))

    report = find(conn, str(fake_project))
    proposal = next(p for p in report.permissions if p.signature == "Bash:npm run")
    assert proposal.calls == 18 and proposal.sessions == 3
    assert proposal.rule == "Bash(npm run:*)"


def test_a_call_an_existing_rule_covers_proposes_nothing(conn, fake_project, fake_home):
    """`Bash(./test.sh)` in settings and `Bash:test.sh` in the transcript are the
    same thing wearing different punctuation. Proposing a rule somebody already
    has is the fastest way to be ignored."""
    for i in range(3):
        add_session(conn, f"s{i}", project_root=str(fake_project),
                    tools=["Bash:test.sh"] * 6 + ["Bash:git status"] * 6)
    config_save(conn, resolve(fake_project, root=fake_home,
                              enterprise=fake_home / "nope.json"))

    report = find(conn, str(fake_project))
    assert [p.signature for p in report.permissions] == []


def test_without_resolved_rules_no_permission_claim_is_made(conn):
    """"No rule covers this" is a claim about every scope. Milestone 2 exists
    because that claim is easy to get wrong, so without a config snapshot it is
    not made at all."""
    for i in range(3):
        add_session(conn, f"s{i}", tools=["Bash:npm run"] * 6)

    report = find(conn, "/work/demo-app")
    assert report.permissions == []
    assert any("atlas config" in note for note in report.notes)


def test_stored_rows_carry_the_pattern_version(conn):
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])
    run_id, is_new = save(conn, find(conn, "/work/demo-app"))
    assert is_new

    row = conn.execute("SELECT pattern_version FROM pattern_runs WHERE id = ?",
                       (run_id,)).fetchone()
    assert row["pattern_version"] == PATTERN_VERSION
    stored = conn.execute("SELECT COUNT(*) n FROM pattern_occurrences WHERE run_id = ?",
                          (run_id,)).fetchone()["n"]
    assert stored > 0, "every occurrence is stored, so the claim survives the session"


def test_an_unchanged_rerun_is_not_a_new_run(conn):
    for i in range(MIN_SUPPORT):
        add_session(conn, f"s{i}", tools=[*noise(i), *RITUAL, *noise(i + 5)])
    first, is_new = save(conn, find(conn, "/work/demo-app"))
    assert is_new
    again, is_new = save(conn, find(conn, "/work/demo-app"))
    assert (again, is_new) == (first, False)
