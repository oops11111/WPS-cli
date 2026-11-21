import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("visibleaudit", ROOT / "scripts/visible_residual_audit.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class VisibleResidualAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = m.extract()
        cls.recorded = json.loads(
            (ROOT / "artifacts/visible-residual-audit-20261121/audit.json").read_text(encoding="utf-8")
        )

    def test_reproduces_recorded_measurements(self):
        actual = json.loads(json.dumps(self.actual))
        # Runtime versions are provenance, not floating measurement tolerances.
        actual.pop("versions")
        expected = dict(self.recorded)
        expected.pop("versions")
        self.assertEqual(actual, expected)

    def test_fixed_score_and_negative_control(self):
        self.assertAlmostEqual(self.actual["whole"], 0.8950000618741911, places=12)
        self.assertEqual(self.actual["repeat_rgb_gray_whole"], self.actual["whole"])
        self.assertTrue(self.actual["negative_same_rgb"])
        self.assertTrue(self.actual["negative_same_gray"])

    def test_disjoint_partition_covers_page_and_conserves_mass(self):
        partitions = self.actual["partitions"]
        self.assertEqual(partitions[0]["raster_y"][0], 0)
        self.assertEqual(partitions[-1]["raster_y"][1], self.actual["size"][1])
        for a, b in zip(partitions, partitions[1:], strict=False):
            self.assertEqual(a["raster_y"][1], b["raster_y"][0])
        self.assertTrue(self.actual["mass_sum_exact"])
        self.assertTrue(self.actual["rgb_partition_sum_exact"])
        self.assertAlmostEqual(sum(p["fraction_mass"] for p in partitions), 1)
        self.assertAlmostEqual(sum(p["rgb_fraction_mass"] for p in partitions), 1)

    def test_fixed_region_mapping_and_actual_ink(self):
        self.assertEqual(self.actual["fixed_roi"]["body"]["raster"], (30, 530, 770, 630))
        self.assertEqual(self.actual["anchors"]["合同总价"]["source"]["first_glyph_ink_raster_rows"], [645, 658])
        self.assertEqual(self.actual["anchors"]["合同总价"]["native"]["first_glyph_ink_raster_rows"], [645, 658])
        self.assertNotEqual(
            self.actual["anchors"]["第四条"]["source"]["first_glyph_ink_raster_rows"],
            self.actual["anchors"]["第四条"]["native"]["first_glyph_ink_raster_rows"],
        )
