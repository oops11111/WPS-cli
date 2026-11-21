"""Verify offline rule-coordinate conventions without running a renderer."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "manual_geometry", Path(__file__).resolve().parents[1] / "scripts/manual_geometry_attribution.py"
)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


class GeometryTests(unittest.TestCase):
    def test_twips(self):
        self.assertEqual(geometry.points("390"), 19.5)

    def test_filled_border_uses_center_and_fill_thickness(self):
        rule = geometry.normalize_rule(dict(x0=10, x1=100, top=20, bottom=20.75, linewidth=0))
        self.assertEqual(rule["position"], 20.375)
        self.assertEqual(rule["thickness"], 0.75)

    def test_stroked_line_uses_center_and_stroke_thickness(self):
        rule = geometry.normalize_rule(dict(x0=10, x1=100, top=20, bottom=20, linewidth=0.72))
        self.assertEqual(rule["position"], 20)
        self.assertEqual(rule["thickness"], 0.72)

    def test_vertical_center(self):
        rule = geometry.normalize_rule(dict(x0=10, x1=10.75, top=20, bottom=40))
        self.assertEqual(rule["axis"], "v")
        self.assertEqual(rule["position"], 10.375)

    def test_background_is_not_border(self):
        self.assertIsNone(geometry.normalize_rule(dict(x0=10, x1=100, top=20, bottom=40)))
