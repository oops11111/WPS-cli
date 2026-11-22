"""Grid-of-link-cards slides keep each card's text in its own place (page 8 of the
Better Codex Designs deck: a ``display:grid`` container whose children are ``<a>``
cards used to collapse into one textbox holding every card's text)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from pptx import Presentation
except ImportError as exc:  # optional test dependency: skip this module instead of erroring the suite
    raise unittest.SkipTest("python-pptx is not installed") from exc

from wps_ai_agent_cli.html_editable import _text
from wps_ai_agent_cli.html_office import convert_html_to_office
from wps_ai_agent_cli.html_slides import collect_slides
from wps_ai_agent_cli.html_styles import has_browser, load

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.card{display:grid;grid-template-columns:40px 1fr 24px}
.cta{display:flex}
</style></head><body>
<section class="slide">
<h2>Cards</h2>
<div class="cards">
<a class="card" href="#"><span class="num">01</span><div><strong>Alpha</strong><p>First card</p><small>alpha</small></div><b>↗</b></a>
<a class="card" href="#"><span class="num">02</span><div><strong>Beta</strong><p>Second card</p><small>beta</small></div><b>↗</b></a>
<a class="card" href="#"><span class="num">03</span><div><strong>Gamma</strong><p>Third card</p><small>gamma</small></div><b>↗</b></a>
<a class="card" href="#"><span class="num">04</span><div><strong>Delta</strong><p>Fourth card</p><small>delta</small></div><b>↗</b></a>
</div>
<a class="cta" href="#">See all cards<span> ↗</span></a>
</section>
</body></html>
"""

CARD_TEXTS = (
    "01",
    "Alpha",
    "First card",
    "alpha",
    "02",
    "Beta",
    "Second card",
    "beta",
    "03",
    "Gamma",
    "Third card",
    "gamma",
    "04",
    "Delta",
    "Fourth card",
    "delta",
)

_NO_BROWSER = mock.patch.dict(os.environ, {"WPS_AGENT_NO_BROWSER": "1"})


def _norm(text: str) -> str:
    return " ".join(text.split())


class GridCardCollectionTests(unittest.TestCase):
    """The cascade (no-browser) collection splits a grid of ``<a>`` cards."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.source = self.work / "grid-cards.html"
        self.source.write_text(HTML, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_grid_cards_split_into_per_card_lines(self):
        with _NO_BROWSER:
            styled = load(self.source, use_browser=False)
        slides = collect_slides(styled.root, styled)
        self.assertEqual(len(slides), 1)
        texts = [_norm(_text(line.node)) for line in slides[0].lines]
        for text in CARD_TEXTS:
            self.assertIn(text, texts, texts)
        for first, second in (("Alpha", "Beta"), ("Alpha", "Gamma"), ("Beta", "Delta")):
            self.assertFalse(
                any(first in text and second in text for text in texts),
                f"one line holds two cards: {texts}",
            )

    def test_flex_link_with_bare_text_still_collapses(self):
        # A flex link whose label is bare text plus a child span must stay one
        # line: its bare text has no browser box of its own, so splitting would
        # strand it and lose the label.
        with _NO_BROWSER:
            styled = load(self.source, use_browser=False)
        slides = collect_slides(styled.root, styled)
        texts = [_norm(_text(line.node)) for line in slides[0].lines]
        self.assertTrue(
            any("See all cards" in text and "↗" in text for text in texts),
            f"the call-to-action label is not one line: {texts}",
        )


@unittest.skipUnless(has_browser(), "the browser layout needs Node.js, Playwright and Edge or Chromium")
class GridCardPositionedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.source = self.work / "grid-cards.html"
        self.source.write_text(HTML, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_card_text_sits_in_its_own_grid_cell(self):
        ok, _data, errors = convert_html_to_office(
            self.source, self.work / "grid-cards.pptx", "pptx", fidelity="appearance"
        )
        self.assertTrue(ok, errors)
        slide = Presentation(self.work / "grid-cards.pptx").slides[0]
        texts = [
            (shape.left, shape.top, shape.text_frame.text)
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        names = {"Alpha", "Beta", "Gamma", "Delta"}
        for _left, _top, text in texts:
            found = names & set(text.split())
            self.assertLessEqual(len(found), 1, f"one textbox mixes cards: {text!r}")
        by_name = {}
        for left, top, text in texts:
            for name in names:
                if text.strip() == name:
                    by_name[name] = (left, top)
        self.assertEqual(set(by_name), names, texts)
        mid = 12192000 / 2
        self.assertLess(by_name["Alpha"][0], mid)
        self.assertGreater(by_name["Beta"][0], mid)
        self.assertGreater(by_name["Gamma"][1], by_name["Alpha"][1])
        self.assertGreater(by_name["Delta"][1], by_name["Beta"][1])
        self.assertTrue(
            any("See all cards" in text for _l, _t, text in texts),
            "the call-to-action label is missing",
        )
