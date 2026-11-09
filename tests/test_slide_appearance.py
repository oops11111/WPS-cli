"""HTML decks written with <div class="slide"> and CSS decoration convert to slides that look like the browser's
(the install report from the P14-005 Windows check, fixtures/html_complex/install-report.html).

The parsing and DrawingML tests need nothing; the conversion tests need Node.js, Playwright and Edge or Chromium
(WPS_AGENT_EDGE) and are skipped without them.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from wps_ai_agent_cli import slide_appearance as look
from wps_ai_agent_cli.html_editable import _TreeParser
from wps_ai_agent_cli.html_slides import collect_slides
from wps_ai_agent_cli.html_styles import color_alpha, has_browser, parse_gradient

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "fixtures" / "html_complex" / "install-report.html"


def _slides(html: str):
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return collect_slides(parser.root)


class PaginationTests(unittest.TestCase):
    def test_a_div_with_the_class_slide_is_a_slide(self):
        slides = _slides(
            '<div class="slide cover"><div class="badge">P14</div><h1>Title</h1><p>a</p></div>'
            '<div class="slide"><h2>Two</h2><p>b</p></div>'
        )
        self.assertEqual(len(slides), 2)
        self.assertTrue(all(slide.section is not None for slide in slides))

    def test_content_before_the_title_of_a_section_stays_on_its_slide(self):
        # The cover's badge before its <h1> used to start a slide of its own, without the section.
        slides = _slides('<section><div class="badge">P14</div><h1>Title</h1><h2>Subtitle</h2></section>')
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].title.tag, "h1")
        self.assertEqual([line.node.tag for line in slides[0].lines], ["div", "h2"])

    def test_without_containers_headings_still_start_slides(self):
        slides = _slides("<h1>One</h1><p>a</p><h2>Two</h2><p>b</p>")
        self.assertEqual([slide.title.tag for slide in slides], ["h1", "h2"])
        self.assertTrue(all(slide.section is None for slide in slides))

    def test_the_install_report_is_four_slides(self):
        slides = _slides(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(len(slides), 4)
        self.assertTrue(all(slide.section is not None for slide in slides))


class ColourAndGradientTests(unittest.TestCase):
    def test_colours_keep_their_opacity(self):
        self.assertEqual(color_alpha("rgba(16, 185, 129, 0.15)"), ("10B981", 0.15))
        self.assertEqual(color_alpha("rgb(1, 2, 3)"), ("010203", 1.0))
        self.assertEqual(color_alpha("rgba(0, 0, 0, 0)"), (None, 0.0))
        self.assertEqual(color_alpha("#fff"), ("FFFFFF", 1.0))

    def test_a_computed_linear_gradient(self):
        gradient = parse_gradient(
            "linear-gradient(135deg, rgb(30, 58, 95) 0%, rgb(15, 23, 42) 50%, rgb(26, 26, 46) 100%)"
        )
        self.assertEqual(gradient["kind"], "linear")
        self.assertEqual(gradient["angle"], 135.0)
        self.assertEqual([stop[2] for stop in gradient["stops"]], [0.0, 0.5, 1.0])

    def test_directions_and_missing_positions(self):
        self.assertEqual(parse_gradient("linear-gradient(rgb(0, 0, 0), rgb(255, 255, 255))")["angle"], 180.0)
        self.assertEqual(parse_gradient("linear-gradient(to right, red, blue)")["angle"], 90.0)
        self.assertEqual(parse_gradient("linear-gradient(to bottom right, red, blue)")["angle"], 135.0)
        self.assertEqual(parse_gradient("linear-gradient(to top left, red, blue)")["angle"], 315.0)
        stops = parse_gradient("linear-gradient(90deg, red, lime, blue)")["stops"]
        self.assertEqual([stop[2] for stop in stops], [0.0, 0.5, 1.0])

    def test_a_radial_fade_to_transparent_keeps_its_colour(self):
        gradient = parse_gradient("radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, rgba(0, 0, 0, 0) 70%)")
        self.assertEqual(gradient["kind"], "radial")
        self.assertEqual(gradient["stops"], [("3B82F6", 0.3, 0.0), ("3B82F6", 0.0, 0.7)])

    def test_no_gradient(self):
        self.assertIsNone(parse_gradient("none"))
        self.assertIsNone(parse_gradient('url("bg.png")'))


class DrawingMLTests(unittest.TestCase):
    def test_a_css_angle_becomes_a_drawingml_angle(self):
        fill = look.gradient_fill(
            {"kind": "linear", "angle": 180.0, "stops": [("000000", 1.0, 0.0), ("FFFFFF", 1.0, 1.0)]}
        )
        self.assertEqual(fill.find(f"{{{look.A}}}lin").get("ang"), str(90 * 60000))  # CSS "to bottom"

    def test_opacity_is_an_alpha(self):
        fill = look.solid_fill("10B981", 0.15)
        self.assertEqual(fill.find(f"{{{look.A}}}srgbClr/{{{look.A}}}alpha").get("val"), "15000")
        self.assertIsNone(look.solid_fill("10B981").find(f"{{{look.A}}}srgbClr/{{{look.A}}}alpha"))

    def test_a_shadow(self):
        shadow = look.parse_shadow("rgba(0, 0, 0, 0.08) 0px 1px 3px 0px", 1.0)
        self.assertEqual((shadow["hue"], shadow["alpha"]), ("000000", 0.08))
        self.assertEqual(shadow["distance"], 9525)
        self.assertEqual(shadow["direction"], 90 * 60000)
        self.assertIsNone(look.parse_shadow("none", 1.0))
        self.assertIsNone(look.parse_shadow("rgba(0, 0, 0, 0.5) 0px 1px 3px 0px inset", 1.0))

    def test_radii_and_borders(self):
        self.assertEqual(look.radius("50%", 40, 40), 20.0)
        self.assertEqual(look.radius("12px", 300, 100), 12.0)
        sides = look.borders(
            {
                "border-left-width": "4px",
                "border-left-style": "solid",
                "border-left-color": "rgb(59, 130, 246)",
                "border-top-width": "0px",
                "border-top-style": "none",
            }
        )
        self.assertEqual(sides, [("left", 4.0, "3B82F6", 1.0)])

    def test_gradient_text_is_not_a_box(self):
        self.assertTrue(
            look.text_is_clipped_background(
                {"-webkit-background-clip": "text", "-webkit-text-fill-color": "rgba(0, 0, 0, 0)"}
            )
        )
        self.assertFalse(look.text_is_clipped_background({"background-clip": "border-box"}))


@unittest.skipUnless(has_browser(), "the browser layout needs Node.js, Playwright and Edge or Chromium")
class InstallReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env = mock.patch.dict(os.environ, {"WPS_AGENT_NO_BROWSER": "0"})
        cls._env.start()
        cls._tmp = tempfile.TemporaryDirectory()
        work = Path(cls._tmp.name)
        shutil.copyfile(REPORT, work / "report.html")
        from wps_ai_agent_cli.html_office import convert_html_to_office

        cls.result = convert_html_to_office(work / "report.html", work / "report.pptx", "pptx", fidelity="appearance")
        cls.editable = convert_html_to_office(work / "report.html", work / "editable.pptx", "pptx")
        cls.path = work / "report.pptx"
        with zipfile.ZipFile(cls.path) as package:
            cls.slides = [package.read(f"ppt/slides/slide{n}.xml").decode("utf-8") for n in range(1, 5)]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        cls._env.stop()

    def test_four_positioned_slides_in_either_mode(self):
        from pptx import Presentation

        ok, data, errors = self.result
        self.assertTrue(ok, errors)
        self.assertEqual(data["slides"], 4)
        self.assertEqual(data["warnings"], [])
        presentation = Presentation(self.path)
        self.assertEqual((presentation.slide_width, presentation.slide_height), (12192000, 6858000))
        self.assertTrue(self.editable[0], self.editable[2])
        self.assertEqual(self.editable[1]["slides"], 4)

    def test_gradient_backgrounds_and_the_cover_glows(self):
        cover, overview, _steps, results = self.slides
        self.assertIn("<p:bg><p:bgPr><a:gradFill", cover)
        self.assertIn('<a:lin ang="2700000"', cover)  # CSS 135deg
        self.assertEqual(cover.count('<a:path path="circle">'), 2)  # ::before and ::after
        self.assertIn('<p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAFC"', overview)
        self.assertIn("<p:bg><p:bgPr><a:gradFill", results)

    def test_the_title_keeps_its_gradient_text_and_alignment(self):
        cover = self.slides[0]
        title = cover[cover.index('type="title"') :]
        self.assertIn('<a:pPr algn="l"/>', title)
        self.assertIn("<a:rPr", title)
        self.assertIn('<a:gs pos="50000"><a:srgbClr val="A78BFA"/>', title)

    def test_cards_steps_and_pills_look_like_the_page(self):
        _cover, overview, steps, _results = self.slides
        self.assertEqual(overview.count('prst="roundRect"'), 4)  # the cards, with shadows
        self.assertEqual(overview.count("<a:outerShdw"), 4)
        for accent in ("3B82F6", "8B5CF6", "10B981", "F59E0B"):
            self.assertIn(f'<a:srgbClr val="{accent}"/>', overview)  # each card's coloured left edge
        self.assertEqual(steps.count('prst="ellipse"'), 9)  # the round step numbers
        self.assertIn('<a:srgbClr val="10B981"><a:alpha val="15000"/>', steps)  # rgba(16,185,129,0.15) pills
        self.assertIn('anchor="ctr"', steps)  # numbers centred in their circles
        self.assertNotIn('wrap="none"', "".join(self.slides))

    def test_a_span_keeps_its_colour_in_the_title(self):
        steps = self.slides[2]
        self.assertIn("步骤", steps)
        span = steps[: steps.index("步骤")]
        self.assertIn('val="3B82F6"', span[span.rindex("<a:r>") :])


if __name__ == "__main__":
    unittest.main()
