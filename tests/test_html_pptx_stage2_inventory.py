"""Fixed-deck source-to-package animation acceptance, independent of playback."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "html_pptx_stage2_inventory.py"
SPEC = importlib.util.spec_from_file_location("html_pptx_stage2_inventory", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
audit, compare = MODULE.audit, MODULE.compare


class FixedAnimationInventoryTests(unittest.TestCase):
    def test_source_intent_is_present_in_package(self):
        cases = audit()["cases"]
        self.assertEqual(sum(len(c["source_slides"]) for c in cases.values()), 12)
        self.assertEqual(sum(len(s["effects"]) for c in cases.values() for s in c["source_slides"]), 13)
        for name, case in cases.items():
            with self.subTest(case=name):
                source_slides = case["source_slides"]
                pptx_slides = case["pptx_slides"]
                self.assertTrue(all(item["status"] == "ooxml_match" for item in case["findings"]))
                self.assertEqual(len(source_slides), len(pptx_slides))
                for source_slide, pptx_slide in zip(source_slides, pptx_slides, strict=True):
                    with self.subTest(case=name, slide=source_slide["slide"]):
                        self.assertEqual(source_slide["transition"], pptx_slide["transition"])
                        self.assertEqual(len(source_slide["effects"]), len(pptx_slide["effects"]))
                        for note in source_slide["notes"]:
                            self.assertIn(note, pptx_slide["notes_xml_text"])
                        for source_effect, target in zip(source_slide["effects"], pptx_slide["effects"], strict=True):
                            kind = {"entrance": "entr", "exit": "exit", "emphasis": "emph"}[source_effect["kind"]]
                            self.assertEqual(kind, target["class"])
                            self.assertEqual(source_effect["duration"], int(target["behavior_duration_ms"]))
                            self.assertTrue(target["targets"])
                            self.assertTrue(target["targets"][0]["shape_text"])

    def test_comparison_rejects_timing_and_target_mismatch(self):
        case = audit()["cases"]["training"]
        broken = copy.deepcopy(case["pptx_slides"])
        broken[1]["effects"][1]["node_type"] = "withEffect"
        broken[1]["effects"][2]["targets"][0]["paragraph_text"] = "wrong item"
        findings = compare(case["source_slides"], broken)
        self.assertEqual(sum(item["status"] == "fail" for item in findings), 2)


if __name__ == "__main__":
    unittest.main()
