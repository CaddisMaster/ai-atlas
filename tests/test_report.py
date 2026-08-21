"""HTML report acceptance tests.

Two things are being protected. The page must be **inert** — it carries project
paths and command signatures, and once it is open in a browser SECURITY.md
cannot follow it, so it may not request anything from anywhere. And it must keep
the honesty the CLI has: a refusal is a state on this page, not an error, and no
screen may grade a session.
"""

import re

from atlas.baseline import build
from atlas.ingest import ingest
from atlas.report import render
from tests.conftest import add_session

# Words the mockup used that the tool cannot support from one session.
JUDGEMENTS = ("going backwards", "going badly", "spiral", "unhealthy", "rarely recover",
              "not holding", "healthy")


def _page(conn, fake_home, fake_project, **kw):
    return render(conn, str(fake_project), root=fake_home, **kw)


def test_the_page_requests_nothing(conn, fake_home, fake_project):
    """No fonts, no scripts, no images, no stylesheets — from anywhere.

    A local report that fetched a webfont would be an outbound request from a
    tool whose first promise is that nothing leaves the machine, made in a
    browser where none of this project's guarantees apply.
    """
    page = _page(conn, fake_home, fake_project)
    assert "http://" not in page and "https://" not in page
    assert "<script" not in page.lower()
    assert not re.search(r'<link[^>]+href', page, re.I)
    assert "src=" not in page


def test_values_from_disk_are_escaped(conn, fake_home, fake_project, tmp_path):
    """Project paths and command signatures end up in this page verbatim, and
    they come off somebody's filesystem."""
    nasty = tmp_path / 'work' / 'demo<script>alert("x")</script>'
    (nasty / ".claude").mkdir(parents=True)
    (nasty / ".claude" / "settings.json").write_text('{"permissions": {"allow": []}}')

    page = render(conn, str(nasty), root=fake_home)
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_a_refusal_is_a_state_and_not_an_error(conn, fake_home, fake_project):
    """One session cannot support a norm, and the page says so plainly."""
    ingest(conn, fake_home)
    page = _page(conn, fake_home, fake_project)

    assert "is not a sample" in page
    assert "No normal band is stated" in page
    # `clay` is the colour reserved for a claim the repository contradicts.
    # Nothing about a refusal may borrow it.
    refusal = page[page.index("What a normal session looks like"):]
    assert "chip clay" not in refusal


def test_no_screen_grades_a_session(conn, fake_home, fake_project):
    """The mockup this design came from said "this session is going backwards".

    A live session is n = 1 (decisions/0009), so the page may state facts and
    place them among earlier sessions, and may not say how it is going.
    """
    ingest(conn, fake_home)
    for i in range(6):
        add_session(conn, f"past{i}", project_root=str(fake_project),
                    user=10, assistant=20, minutes=60.0, tools=["Bash:git status"] * 40)

    page = _page(conn, fake_home, fake_project).lower()
    for word in JUDGEMENTS:
        assert word not in page, f"the page must not say {word!r} about a session"


def test_every_configured_item_carries_its_source(conn, fake_home, fake_project):
    page = _page(conn, fake_home, fake_project)
    assert str(fake_project / ".claude" / "settings.json") in page
    assert str(fake_project / ".claude" / "agents" / "sweeper.md") in page
    assert "could not be read" in page, "the unknown scope is explained, not hidden"


def test_the_synthetic_banner_is_only_there_when_asked(conn, fake_home, fake_project):
    assert "Synthetic corpus" not in _page(conn, fake_home, fake_project)
    assert "Synthetic corpus" in _page(conn, fake_home, fake_project, synthetic=True)


def test_the_page_is_balanced_html(conn, fake_home, fake_project):
    """Generated markup, so nothing checks it but this."""
    from html.parser import HTMLParser

    void = {"meta", "link", "br", "hr", "img", "input", "source", "col"}

    class Balance(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.bad = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if not self.stack:
                self.bad.append(f"stray </{tag}>")
            elif self.stack[-1] == tag:
                self.stack.pop()
            else:
                self.bad.append(f"</{tag}> closes <{self.stack[-1]}>")

    ingest(conn, fake_home)
    parser = Balance()
    parser.feed(_page(conn, fake_home, fake_project))
    assert parser.stack == [] and parser.bad == []


def test_the_numbers_match_the_library(conn, fake_home, fake_project):
    """The page renders what the tool computed — it does not recompute anything
    its own way, which is how two screens start disagreeing."""
    ingest(conn, fake_home)
    for i in range(6):
        add_session(conn, f"past{i}", project_root=str(fake_project),
                    user=10, assistant=20, minutes=60.0, tools=["Bash:git status"] * 40)

    base = build(conn, str(fake_project))
    page = _page(conn, fake_home, fake_project)
    assert f'<div class="v">{base.n}</div>' in page
    assert base.confidence in page
