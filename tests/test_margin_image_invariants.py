"""Pre-registered semantic image invariants, independent of Stage27 results."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("image_gate", ROOT / "scripts/qualified_margin_acceptance.py")
m = importlib.util.module_from_spec(SPEC)
with patch("sys.path", [str(ROOT / "scripts"), *sys.path]):
    SPEC.loader.exec_module(m)


class ImageAlignmentInvariantTests(unittest.TestCase):
    def test_center_and_left_have_different_invariants(self):
        center = {"x0": 177.6, "top": 241.2, "width": 240, "height": 120}
        browser = {**center, "x0": 178.5}
        self.assertTrue(m.image_invariant("center", center, center, browser, 34.32, 33.72, 297.65, 297.65))
        self.assertFalse(
            m.image_invariant("center", center, {**center, "x0": 177}, browser, 34.32, 33.72, 297.65, 297.65)
        )
        a = {**center, "x0": 64.32}
        b = {**a, "x0": 63.72}
        self.assertTrue(m.image_invariant("left", a, b, a, 34.32, 33.72, 297.65, 297.65))
        self.assertFalse(m.image_invariant("left", a, a, a, 34.32, 33.72, 297.65, 297.65))

    def test_alignment_qualification_fails_closed(self):
        self.assertEqual(m.alignment_mode("center", "center", "center", 33.75, 33.75, {}), "center")
        self.assertEqual(m.alignment_mode("start", "left", "left", 34.35, 34.35, {"left": "600"}), "left")
        for args in [
            ("center", "center", "center", 33.75, 34.35, {}),
            ("center", "center", "center", 33.75, 33.75, {"left": "1"}),
            ("left", "left", "center", 33.75, 33.75, {}),
            ("unknown", "center", "center", 33.75, 33.75, {}),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.alignment_mode(*args)

    def test_size_y_and_browser_error_regressions_rejected(self):
        a = {"x0": 100, "top": 20, "width": 50, "height": 30}
        for b in ({**a, "top": 21}, {**a, "height": 31}, {**a, "x0": 101}):
            self.assertFalse(m.image_invariant("center", a, b, a, 0, 0, 125, 125))


if __name__ == "__main__":
    unittest.main()
