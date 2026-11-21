import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("visibleaudit", ROOT / "scripts/visible_residual_audit.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def portable_hash_keys(record):
    result = dict(record)
    result["hashes"] = {key.replace("\\", "/"): value for key, value in record["hashes"].items()}
    if len(result["hashes"]) != len(record["hashes"]):
        raise ValueError("Ambiguous normalized provenance paths")
    return result


def measurement_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, float):
        return math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9)
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(measurement_equal(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(
            measurement_equal(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return actual == expected


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
        self.assertTrue(measurement_equal(portable_hash_keys(actual), portable_hash_keys(expected)))

    def test_only_float_measurements_use_absolute_tolerance(self):
        self.assertTrue(measurement_equal({"value": [0.8950000618741908]}, {"value": [0.8950000618741911]}))
        self.assertFalse(measurement_equal(0.895, 0.895000002))
        for a, b in ((1, True), (1, 1.0), ("hash", "other"), ([1], [1, 2]), ({"x": 1}, {"y": 1})):
            self.assertFalse(measurement_equal(a, b))

    def test_only_provenance_path_separators_are_normalized(self):
        a = {"hashes": {"artifacts\\case\\input.pdf": "exact-digest"}, "whole": 0.895}
        b = {"hashes": {"artifacts/case/input.pdf": "exact-digest"}, "whole": 0.895}
        self.assertEqual(portable_hash_keys(a), b)
        self.assertNotEqual(portable_hash_keys(a), {**b, "whole": 0.896})
        self.assertNotEqual(portable_hash_keys(a), {**b, "hashes": {"artifacts/case/input.pdf": "other-digest"}})
        self.assertEqual(a["hashes"], {"artifacts\\case\\input.pdf": "exact-digest"})
        with self.assertRaises(ValueError):
            portable_hash_keys({"hashes": {"a\\b": "one", "a/b": "two"}})

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
