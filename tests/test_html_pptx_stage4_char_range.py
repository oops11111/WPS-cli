"""Verify the Stage4 disposable character-range candidate against its source."""

from __future__ import annotations

import importlib.util
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/html_pptx_stage4_char_range_probe.py"
SPEC = importlib.util.spec_from_file_location("html_pptx_stage4_char_range_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CharacterRangeCandidateTests(unittest.TestCase):
    def test_candidate_changes_only_slide5_timing_target(self):
        original = ROOT / "artifacts/html-pptx-stage3-20261122/A-launch-pptx/candidate.pptx"
        candidate = ROOT / "artifacts/html-pptx-inline-stage4-20261122/launch-char-range-candidate.pptx"
        with zipfile.ZipFile(original) as a, zipfile.ZipFile(candidate) as b:
            self.assertEqual(a.namelist(), b.namelist())
            changed = [name for name in a.namelist() if a.read(name) != b.read(name)]
            self.assertEqual(changed, [MODULE.SLIDE])
            before = a.read(MODULE.SLIDE)
            after = b.read(MODULE.SLIDE)
            self.assertEqual(before.split(b"<p:timing", 1)[0], after.split(b"<p:timing", 1)[0])
            root = ET.fromstring(after)
            targets = [node for node in root.iter(f"{MODULE.P}charRg")]
            self.assertEqual([(node.get("st"), node.get("end")) for node in targets], [("10", "15")] * 2)

    def test_non_bmp_prefix_changes_offset_units(self):
        self.assertEqual(len("🚀 A"), 3)
        self.assertEqual(MODULE.utf16_length("🚀 A"), 4)


if __name__ == "__main__":
    unittest.main()
