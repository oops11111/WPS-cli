"""The layout gate must compare complete slide canvases and preserve old scores."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from wps_ai_agent_cli import fidelity
from wps_ai_agent_cli.html_styles import has_browser, load

ROOT = Path(__file__).resolve().parents[1]


class FullSlideScoreTests(unittest.TestCase):
    def setUp(self):
        self.source = Image.new("L", (128, 72), 255)
        ImageDraw.Draw(self.source).rectangle((0, 0, 39, 9), fill=0)
        self.legacy = Image.new("L", (126, 12), 255)
        ImageDraw.Draw(self.legacy).rectangle((0, 0, 39, 9), fill=0)
        self.target = Image.new("L", (80, 45), 255)
        ImageDraw.Draw(self.target).rectangle((0, 0, 24, 5), fill=0)

    def test_full_canvas_and_legacy_score_are_separate(self):
        capture = {"status": "measured", "canvas": [1280, 720], "normalization": "section is slide"}
        with (
            patch.object(fidelity, "_html_slide_images", return_value=([self.source], [self.legacy], capture, None)),
            patch.object(fidelity, "_images_for", return_value=([self.target], None)),
            patch.object(fidelity, "missing_fonts", return_value=[]),
        ):
            result = fidelity.score_layout(Path("source.html"), Path("target.pptx"), renderer="wps")
        self.assertEqual(result["status"], "measured")
        self.assertEqual(result["canvas_mode"], "browser-native-1280x720-slide-viewport")
        self.assertGreater(result["score"], result["legacy_score"])
        self.assertEqual(result["source_capture"], capture)

    def test_different_target_aspect_ratio_fails_closed(self):
        with (
            patch.object(fidelity, "_html_slide_images", return_value=([self.source], [self.legacy], {}, None)),
            patch.object(fidelity, "_images_for", return_value=([Image.new("L", (80, 60), 255)], None)),
        ):
            result = fidelity.score_layout(Path("source.html"), Path("target.pptx"), renderer="wps")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("different aspect ratios", result["reason"])


@unittest.skipUnless(has_browser(), "needs Node.js, Playwright and Edge/Chromium")
class BrowserSlideCanvasTests(unittest.TestCase):
    def test_three_fixed_decks_keep_section_geometry_without_clipping(self):
        cases = (
            ("html_complex/launch.html", 6, True),
            ("fidelity/training.html", 3, False),
            ("fidelity/quarterly.html", 3, False),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for name, count, short_sections in cases:
                with self.subTest(name=name):
                    folder = Path(temporary) / Path(name).stem
                    sections, slides = folder / "sections", folder / "slides"
                    sections.mkdir(parents=True)
                    slides.mkdir()
                    styled = load(
                        ROOT / "fixtures" / name,
                        screenshots_dir=sections,
                        slide_screenshots_dir=slides,
                        viewport=(1280, 720),
                    )
                    self.assertEqual(styled.slide_capture["status"], "measured")
                    self.assertEqual(len(styled.slide_screenshots), count)
                    self.assertEqual(len(styled.section_screenshots), count)
                    self.assertEqual(len(styled.slide_capture["proofs"]), count)
                    for original, proof, screenshot in zip(
                        styled.slide_capture["original"],
                        styled.slide_capture["proofs"],
                        styled.slide_screenshots,
                        strict=True,
                    ):
                        self.assertEqual(Image.open(screenshot).size, (1280, 720))
                        self.assertAlmostEqual(original["width"], proof["width"], delta=1)
                        self.assertAlmostEqual(original["height"], proof["height"], delta=1)
                        self.assertAlmostEqual(proof["left"], 0, delta=1)
                        self.assertAlmostEqual(proof["top"], 0, delta=1)
                        self.assertFalse(proof["leaking"])
                    section_heights = [Image.open(name).height for name in styled.section_screenshots]
                    self.assertEqual(any(height < 720 for height in section_heights), short_sections)


if __name__ == "__main__":
    unittest.main()
